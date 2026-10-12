"""Fonctions métier pour construire et enregistrer zones.toml."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import Literal, TypedDict, TypeGuard, cast
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

FAMILY_NAMES = ("cultural", "physical", "raster")
PRECISION_ORDER: tuple[Precision, ...] = ("high", "medium", "low")
PRECISION_TO_RESOLUTION = {"high": 10, "medium": 50, "low": 110}
SOURCE_PATH = "https://naturalearth.s3.amazonaws.com"

Family = Literal["cultural", "physical", "raster"]
Precision = Literal["high", "medium", "low"]
SaveMode = Literal["replace", "dated"]


@dataclass(frozen=True)
class Dataset:
    """Jeu de données validé du catalogue Natural Earth."""

    family: Family
    identifier: str
    name: str
    precisions: tuple[Precision, ...]
    link_part: str
    description: str


@dataclass(frozen=True)
class DatasetSelection:
    """Jeu de données accompagné des précisions retenues."""

    dataset: Dataset
    precisions: tuple[Precision, ...]


class FamilyEntry(TypedDict):
    """Entrée d'une famille de données dans le catalogue."""
    name: str
    precision: list[str]
    link: str


class ZoneMapping(TypedDict):
    """Correspondance entre un code de zone et sa géométrie et ses classes."""
    name: str
    code: str
    geometry: str
    class_: str
    classes: dict[str, str]


class DataFamily(TypedDict):
    """Familles de données disponibles dans le catalogue."""
    cultural: list[FamilyEntry]
    physical: list[FamilyEntry]
    raster: list[FamilyEntry]
    mapping: dict[str, dict[str, object]]


class ZonesConfig(TypedDict):
    """Configuration des zones, incluant le chemin source et les familles de données."""
    source_path: str
    data_family: DataFamily


def _as_object_mapping(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} doit être un objet aux clés textuelles.")
    raw_values = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw_values):
        raise ValueError(f"{context} doit être un objet aux clés textuelles.")
    return {
        key: item
        for key, item in raw_values.items()
        if isinstance(key, str)
    }


def _required_string(values: Mapping[str, object], key: str, context: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} : champ {key!r} absent ou invalide.")
    return value


def _family(value: str) -> Family:
    if value not in FAMILY_NAMES:
        raise ValueError(f"Famille inconnue : {value!r}.")
    return value


def _precision(value: str, context: str) -> Precision:
    if value not in PRECISION_TO_RESOLUTION:
        raise ValueError(f"Précision inconnue dans {context} : {value!r}.")
    return cast(Precision, value)


def is_precision(value: object) -> TypeGuard[Precision]:
    """Indique si une valeur appartient aux précisions connues."""
    return isinstance(value, str) and value in PRECISION_TO_RESOLUTION


def _validate_link_part(link_part: str) -> None:
    if (
        PurePosixPath(link_part).name != link_part
        or "\\" in link_part
        or link_part in {".", ".."}
    ):
        raise ValueError(f"Identifiant de lien non sûr : {link_part!r}.")


def _parse_dataset(raw_entry: object, family: Family, index: int) -> Dataset:
    context = f"Entrée {index} de {family}"
    entry = _as_object_mapping(raw_entry, context)
    name = _required_string(entry, "name", context)
    link_part = _required_string(entry, "link_part", context)
    _validate_link_part(link_part)

    raw_precisions = entry.get("precision")
    if not isinstance(raw_precisions, list) or not raw_precisions:
        raise ValueError(f"{context} doit définir au moins une précision.")
    precision_values: list[Precision] = []
    for raw_precision in cast(list[object], raw_precisions):
        if not isinstance(raw_precision, str):
            raise ValueError(f"Précisions invalides dans {context}.")
        precision_values.append(_precision(raw_precision, context))
    precisions = tuple(precision_values)

    raw_identifier = entry.get("id", link_part)
    if not isinstance(raw_identifier, str) or not raw_identifier:
        raise ValueError(f"{context} : identifiant invalide.")
    raw_description = entry.get("description", "")
    if not isinstance(raw_description, str):
        raise ValueError(f"{context} : description invalide.")
    return Dataset(
        family=family,
        identifier=raw_identifier,
        name=name,
        precisions=precisions,
        link_part=link_part,
        description=raw_description,
    )


def load_catalog(catalog_path: Path) -> list[Dataset]:
    """Charge et valide les jeux de données du catalogue JSON.

    Args:
        catalog_path: Chemin vers le catalogue Natural Earth.

    Returns:
        Les jeux de données valides, dans l’ordre du catalogue.

    Raises:
        OSError: Si le catalogue est illisible.
        ValueError: Si sa structure ou une entrée est invalide.
    """
    try:
        raw_catalog: object = json.loads(catalog_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Catalogue JSON invalide : {error}.") from error
    catalog = _as_object_mapping(raw_catalog, "Le catalogue")

    datasets: list[Dataset] = []
    for family_name in FAMILY_NAMES:
        entries = catalog.get(family_name, [])
        if not isinstance(entries, list):
            raise ValueError(f"La famille {family_name!r} doit être une liste.")
        family = _family(family_name)
        raw_entries = cast(list[object], entries)
        datasets.extend(
            _parse_dataset(entry, family, index)
            for index, entry in enumerate(raw_entries)
        )
    return datasets


def build_zones_config(
    selections: Iterable[DatasetSelection],
    mappings: Mapping[str, Mapping[str, object]] | None = None,
    source_path: str = SOURCE_PATH,
) -> ZonesConfig:
    """Construit le dictionnaire TOML à partir des sélections et mappings."""
    if not source_path.strip():
        raise ValueError("L’adresse source ne peut pas être vide.")

    data_family: DataFamily = {
        "cultural": [],
        "physical": [],
        "raster": [],
        "mapping": {},
    }
    selected_links: set[str] = set()
    for selection in selections:
        dataset = selection.dataset
        if not selection.precisions:
            raise ValueError(f"Aucune précision retenue pour {dataset.name!r}.")
        if not set(selection.precisions).issubset(dataset.precisions):
            raise ValueError(f"Précision indisponible pour {dataset.name!r}.")
        if dataset.link_part in selected_links:
            raise ValueError(f"Identifiant sélectionné plusieurs fois : {dataset.link_part!r}.")
        selected_links.add(dataset.link_part)
        data_family[dataset.family].append(
            {
                "name": dataset.name,
                "precision": sorted(selection.precisions, key=PRECISION_ORDER.index),
                "link": dataset.link_part,
            }
        )

    for link, mapping in (mappings or {}).items():
        if link in selected_links:
            data_family["mapping"][link] = dict(mapping)
    return {"source_path": source_path, "data_family": data_family}


def validate_mapping(mapping: Mapping[str, object]) -> list[str]:
    """Retourne les erreurs d’un mapping destiné à une entrée TOML."""
    errors: list[str] = []
    for field in ("name", "code", "geometry", "class"):
        value = mapping.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"Le champ {field!r} est obligatoire.")
    classes = mapping.get("classes")
    if not isinstance(classes, dict):
        errors.append("Le champ 'classes' doit être un dictionnaire.")
    else:
        class_values = cast(dict[object, object], classes)
        if any(
            not isinstance(source, str)
            or not source
            or not isinstance(target, str)
            or not target.strip()
            for source, target in class_values.items()
        ):
            errors.append("Chaque classe doit avoir une valeur source et une cible.")
    return errors


def validate_zones_config(config: ZonesConfig) -> list[str]:
    """Retourne les erreurs qui empêchent l’export de la configuration."""
    errors: list[str] = []
    selected_links: list[str] = []
    for family in FAMILY_NAMES:
        for entry in config["data_family"][family]:
            link = entry["link"]
            selected_links.append(link)
            mapping = config["data_family"]["mapping"].get(link)
            if mapping is None:
                errors.append(f"Mapping manquant pour {entry['name']!r}.")
            else:
                errors.extend(
                    f"{entry['name']} : {error}"
                    for error in validate_mapping(mapping)
                )
    if len(selected_links) != len(set(selected_links)):
        errors.append("Plusieurs sélections partagent le même identifiant de mapping.")
    if not selected_links:
        errors.append("Aucun jeu de données n’est sélectionné.")
    return errors


def zones_config_to_toml(config: ZonesConfig) -> str:
    """Sérialise la configuration et vérifie le TOML produit."""
    import tomli_w  # pylint: disable=C0415, E0401

    serialized = tomli_w.dumps(config)
    import tomllib  # pylint: disable=C0415

    tomllib.loads(serialized)
    return serialized


def save_zones_config(
    config: ZonesConfig,
    zones_path: Path,
    mode: SaveMode,
    today: date | None = None,
) -> Path:
    """Enregistre la configuration vers le chemin explicitement choisi."""
    errors = validate_zones_config(config)
    if errors:
        raise ValueError("Configuration incomplète : " + " ".join(errors))

    target = zones_path
    if mode == "dated":
        file_date = today or date.today()
        target = zones_path.with_name(f"{file_date:%y-%m-%d}_zones.toml")

    serialized = zones_config_to_toml(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "dated":
        with target.open("x", encoding="utf-8") as output_file:
            output_file.write(serialized)
        return target

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as output_file:
            temporary_name = output_file.name
            output_file.write(serialized)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary_name, target)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
    return target


def resolve_selected_shapefile( # pylint: disable=R0914
    dataset: Dataset,
    precision: Precision,
    data_path: Path,
    source_path: str = SOURCE_PATH,
) -> Path:
    """Retourne le SHP local ou télécharge l’archive du seul jeu demandé."""
    _validate_link_part(dataset.link_part)
    resolution = PRECISION_TO_RESOLUTION[precision]
    dataset_path = data_path / dataset.family / f"{resolution}m" / dataset.link_part
    shapefiles = sorted(dataset_path.glob("*.shp")) if dataset_path.exists() else []
    if len(shapefiles) > 1:
        raise ValueError(f"Plusieurs shapefiles trouvés dans {dataset_path}.")
    if shapefiles:
        return shapefiles[0]

    archive_name = (
        f"{dataset.link_part}.zip"
        if dataset.family == "raster"
        else f"ne_{resolution}m_{dataset.link_part}.zip"
    )
    request = Request(
        f"{source_path.rstrip('/')}/{resolution}m_{dataset.family}/{archive_name}",
        headers={"User-Agent": "GeoReforge/1.0"},
    )
    with urlopen(request, timeout=60) as response:
        archive_content = response.read()

    dataset_path.mkdir(parents=True, exist_ok=True)
    extraction_root = dataset_path.resolve()
    try:
        with ZipFile(io.BytesIO(archive_content)) as archive:
            for member in archive.infolist():
                normalized_name = member.filename.replace("\\", "/")
                member_path = PurePosixPath(normalized_name)
                mode = member.external_attr >> 16
                target_path = (dataset_path / Path(*member_path.parts)).resolve()
                if (
                    member_path.is_absolute()
                    or ".." in member_path.parts
                    or not target_path.is_relative_to(extraction_root)
                ):
                    raise ValueError(f"Chemin non sûr dans l’archive : {member.filename!r}.")
                if stat.S_ISLNK(mode):
                    raise ValueError(f"Lien symbolique inattendu : {member.filename!r}.")
            archive.extractall(dataset_path)
    except BadZipFile as error:
        raise ValueError(f"Archive ZIP invalide pour {dataset.name!r}.") from error

    shapefiles = sorted(dataset_path.glob("*.shp"))
    if len(shapefiles) != 1:
        raise ValueError(
            f"Un shapefile attendu dans {dataset_path}, trouvé : {len(shapefiles)}."
        )
    return shapefiles[0]
