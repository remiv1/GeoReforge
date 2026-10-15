"""Downloads and extracts the archives described in the Natural Earth catalog.

.. classes::
    - `DownloadTask`: Represents a download task for an archive and its extraction destination.
    - `_ArgumentDefaultsRawDescriptionHelpFormatter`: Custom argument parser help formatter.

.. functions::
    - `build_tasks`: Build download tasks from the catalog.
    - `_build_family_tasks`: Build download tasks for a specific family from the catalog.
    - `_build_entry_tasks`: Build download tasks for a specific entry within a family.
    - `_validate_archive`: Validate the contents of a downloaded archive.
    - `download_and_extract`: Download an archive and extract its contents.
    - `parse_arguments`: Parse command-line arguments for the script.
    - `download_all`: Download and extract all tasks from the catalog.
    - `main`: Entry point for the script.

.. constants::
    - `PROJECT_ROOT`: The root directory of the project.
    - `DEFAULT_CATALOG_PATH`: Default path to the Natural Earth catalog JSON file.
    - `DEFAULT_OUTPUT_PATH`: Default output directory for extracted archives.
    - `BASE_URL`: Base URL for downloading Natural Earth archives.
    - `PRECISION_TO_RESOLUTION`: Mapping from precision levels to resolution values.
    - `FAMILIES`: Tuple of family names in the catalog.

.. note::
    This script is used to download and extract Natural Earth archives based on a JSON catalog.
    It's used to explore and make researches on Natural Earth data. This script isn't used
    for production purposes.

.. usage::
    ```bash
    python scripts/download_naturalearth.py [--catalog CATALOG_PATH] [--output OUTPUT_PATH]
    ```

.. args::
    - `--catalog CATALOG_PATH`: Path to the Natural Earth catalog JSON file.
    Defaults to `DEFAULT_CATALOG_PATH`.
    - `--output OUTPUT_PATH`: Output directory for extracted archives.
    Defaults to `DEFAULT_OUTPUT_PATH`.
    - `--timeout TIMEOUT`: Timeout in seconds for downloading each archive. Defaults to `30`.
    - `--workers WORKERS`: Number of concurrent download workers. Defaults to `4`.
    - `--dry-run`: Perform a dry run without actually downloading or extracting archives.
    Defaults to `False`.
    
.. module_author:: Rémi Verschuur <rvershuur@audit-io.fr>
.. version:: 1.0.0
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
from textwrap import dedent
from typing import Any
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "src" / "naturalearth.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "tmp"
BASE_URL = "https://naturalearth.s3.amazonaws.com"
PRECISION_TO_RESOLUTION = {"high": 10, "medium": 50, "low": 110}
FAMILIES = ("cultural", "physical", "raster")


class _ArgumentDefaultsRawDescriptionHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    pass


@dataclass(frozen=True)
class DownloadTask:
    """Archive à récupérer et destination de son contenu extrait."""

    family: str
    precision: str
    link_part: str
    url: str
    destination: Path


def build_tasks(catalog_path: Path, output_path: Path) -> list[DownloadTask]:
    """Construit les téléchargements à partir du catalogue JSON."""
    catalog: Any = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict):
        raise ValueError("Le catalogue doit être un objet JSON par famille.")

    tasks: list[DownloadTask] = []
    for family in FAMILIES:
        tasks.extend(_build_family_tasks(family, catalog, output_path))  # type: ignore

    destinations = [task.destination for task in tasks]
    if len(destinations) != len(set(destinations)):
        raise ValueError("Le catalogue produit plusieurs archives vers le même dossier.")
    return tasks


def _build_family_tasks(
    family: str, catalog: dict[str, Any], output_path: Path
) -> list[DownloadTask]:
    entries = catalog.get(family, [])
    if not isinstance(entries, list):
        raise ValueError(f"La famille {family!r} doit contenir une liste.")
    tasks: list[DownloadTask] = []
    for entry in entries:   # type: ignore
        tasks.extend(_build_entry_tasks(family, entry, output_path))
    return tasks


def _build_entry_tasks(
    family: str, entry: Any, output_path: Path
) -> list[DownloadTask]:
    if not isinstance(entry, dict):
        raise ValueError(f"Entrée invalide dans la famille {family!r}.")
    link_part = entry.get("link_part", "")  # type: ignore
    precisions = entry.get("precision", [])  # type: ignore
    if not isinstance(link_part, str) or not link_part:
        raise ValueError(f"link_part manquant dans la famille {family!r}.")
    if (
        PurePosixPath(link_part).name != link_part
        or "\\" in link_part
        or link_part in {".", ".."}
    ):
        raise ValueError(f"link_part non sûr : {link_part!r}.")
    if not isinstance(precisions, list) or not precisions:
        raise ValueError(f"Précision manquante pour {link_part!r}.")

    tasks: list[DownloadTask] = []
    for precision in precisions:  # type: ignore
        if precision not in PRECISION_TO_RESOLUTION:
            raise ValueError(
                f"Précision inconnue pour {link_part!r} : {precision!r}."
            )
        resolution = PRECISION_TO_RESOLUTION[precision]
        filename = (
            f"{link_part}.zip"
            if family == "raster"
            else f"ne_{resolution}m_{link_part}.zip"
        )
        url = f"{BASE_URL}/{resolution}m_{family}/{filename}"
        destination = output_path / family / f"{resolution}m" / link_part
        tasks.append(
            DownloadTask(
                family=family,
                precision=precision,  # type: ignore
                link_part=link_part,
                url=url,
                destination=destination,
            )
        )
    return tasks


def _validate_archive(archive: ZipFile, extraction_path: Path) -> None:
    """Refuse les chemins sortant du dossier d’extraction et les liens symboliques."""
    extraction_root = extraction_path.resolve()
    for member in archive.infolist():
        normalized_name = member.filename.replace("\\", "/")
        member_path = PurePosixPath(normalized_name)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise ValueError(f"Chemin non sûr dans l’archive : {member.filename!r}.")
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ValueError(f"Lien symbolique inattendu : {member.filename!r}.")
        target_path = (extraction_path / Path(*member_path.parts)).resolve()
        if not target_path.is_relative_to(extraction_root):
            raise ValueError(f"Chemin non sûr dans l’archive : {member.filename!r}.")


def download_and_extract(task: DownloadTask, output_path: Path, timeout: int) -> str:
    """Télécharge une archive, l’extrait, puis élimine les fichiers temporaires."""
    if task.destination.exists():
        return "déjà présent"

    task.destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=".naturalearth-", dir=output_path) as temp_dir:
            staging_path = Path(temp_dir)
            archive_path = staging_path / "download.zip"
            extraction_path = staging_path / "contents"
            request = Request(task.url, headers={"User-Agent": "GeoReforge/1.0"})
            with (
                urlopen(request, timeout=timeout) as response,
                archive_path.open("wb") as archive_file,
            ):
                shutil.copyfileobj(response, archive_file)

            with ZipFile(archive_path) as archive:
                _validate_archive(archive, extraction_path)
                archive.extractall(extraction_path)

            task.destination.parent.mkdir(parents=True, exist_ok=True)
            extraction_path.rename(task.destination)
        return "téléchargé"
    except (BadZipFile, OSError, ValueError) as error:
        return f"échec: {error}"


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and extract Natural Earth archives from a JSON catalog.",
        formatter_class=_ArgumentDefaultsRawDescriptionHelpFormatter,
        epilog=dedent(
            """\
            Examples:
              python scripts/download_naturalearth.py --dry-run
              python scripts/download_naturalearth.py --catalog src/naturalearth.json --output tmp

            Note:
              This utility is for exploring Natural Earth data; it is not used in production.

            Version: 1.0.0
            Author: Rémi Verschuur <rverschuur@audit-io.fr>
            """
        ),
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
        help="Path to the Natural Earth JSON catalog.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Directory where archives are extracted.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Download timeout in seconds.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent downloads.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List planned URLs without downloading or extracting archives.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )
    args = parser.parse_args()
    if args.timeout <= 0 or args.workers <= 0:
        parser.error("--timeout et --workers doivent être supérieurs à zéro.")
    return args


def _download_all(
    tasks: list[DownloadTask], output_path: Path, workers: int, timeout: int
) -> tuple[int, int, list[tuple[DownloadTask, str]]]:
    failures: list[tuple[DownloadTask, str]] = []
    downloaded = 0
    skipped = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(download_and_extract, task, output_path, timeout): task
            for task in tasks
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            task = futures[future]
            status = future.result()
            if status == "téléchargé":
                downloaded += 1
            elif status == "déjà présent":
                skipped += 1
            else:
                failures.append((task, status))
            if completed % 25 == 0 or completed == len(tasks):
                print(f"Avancement : {completed}/{len(tasks)} archives traitées.")
    return downloaded, skipped, failures


def main() -> int:
    """Exécute le téléchargement et retourne un code de sortie exploitable."""
    args = _parse_arguments()
    try:
        tasks = build_tasks(args.catalog, args.output)
    except (OSError, ValueError) as error:
        print(f"Erreur de catalogue : {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"{len(tasks)} archives prévues depuis {args.catalog}.")
        for task in tasks:
            print(task.url)
        return 0

    args.output.mkdir(parents=True, exist_ok=True)
    downloaded, skipped, failures = _download_all(
        tasks, args.output, args.workers, args.timeout
    )

    print(
        f"Bilan : {downloaded} téléchargées, {skipped} déjà présentes, "
        f"{len(failures)} échecs."
    )
    for task, failure in failures:
        print(f"{failure} : {task.url}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
