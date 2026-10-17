"""Download configured geographic datasets and expose their import metadata.

.. classes::
    - `DataImporter`: Loads dataset settings and downloads source files.

.. constants::
    - `DEFAULT_DOWNLOAD_PATH`: The default path where data files are downloaded.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

import os
import logging
import io
import tomllib
from pathlib import Path
from typing import Any, Optional
from zipfile import BadZipFile, ZipFile

import requests

from ..other_objects import Precision, PRECISION_MAP, DataTheme

DEFAULT_DOWNLOAD_PATH = Path("/tmp/app/")
LOGGER = logging.getLogger(__name__)

class DataImporter:
    """Load dataset settings and download their source files.

    :param file_path: Optional path to the TOML configuration file.
    :type file_path: str | Path | None

    .. methods::
        - `__init__`: Load and parse a TOML configuration.
        - `_append_data_theme`: Create a data theme for each configured resolution.
        - `download_files`: Download and extract shapefile components.
        - `list_downloaded_files`: List downloaded files, optionally by extension.
        - `clear_downloaded_files`: Remove downloaded files.

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
    """
    def __init__(self, file_path: str | Path | None = None) -> None:
        """Initialize the importer from a TOML configuration.

        :param file_path: Optional path to the TOML configuration file.
        :type file_path: str | Path | None

        :return: None.
        :rtype: None

        :raises OSError: If the configuration file cannot be read.
        :raises tomllib.TOMLDecodeError: If the configuration is invalid TOML.
        :raises KeyError: If a required configuration key is missing.
        """
        config_path = file_path or os.environ.get(
            "ZONES_CONFIG_PATH",
            "/etc/app/zones.toml",
        )
        with open(config_path, "rb") as _f:
            f = tomllib.load(_f)
        self.url_base = f["source_path"]
        self.data_themes: list[DataTheme] = []
        zones = f["data_family"]
        self.mapping = zones.get("mapping", {})
        self._append_data_theme(list(zones.get("cultural", [])), "cultural")
        self._append_data_theme(list(zones.get("physical", [])), "physical")
        self._append_data_theme(list(zones.get("raster", [])), "raster")

    def _append_data_theme(self, zone_list: list[dict[str, Any]], zone_name: str) -> None:
        """Append dataset configurations for one data family.

        :param zone_list: Dataset configurations from a TOML family section.
        :type zone_list: list[dict[str, Any]]
        :param zone_name: Data family name, such as ``cultural`` or ``physical``.
        :type zone_name: str
        :return: None.
        :rtype: None

        :raises KeyError: If a dataset configuration is missing its name.
        """
        for dt in zone_list:
            for precision in dt.get("precision", ["high"]):
                scale = PRECISION_MAP.get(precision, Precision.HIGH).value
                route = (
                    f'{self.url_base}/{scale}m_{zone_name}/ne_{scale}m_{dt.get("link", "")}.zip'
                )
                self.data_themes.append(
                    DataTheme(
                        name=dt["name"],
                        data_family=zone_name,
                        precision=precision,
                        link=dt.get("link", ""),
                        source_path=self.url_base,
                        mapping=self.mapping.get(dt.get("link", ""), {}),
                        url_route=route,
                    )
                )

    def download_files(self, download_path: Path = DEFAULT_DOWNLOAD_PATH) -> 'DataImporter':
        """Download and extract shapefile components for configured datasets.

        :param download_path: The directory to download files to.
        :type download_path: Path
        :returns: The instance of the `DataImporter` after downloading files.
        :rtype: 'DataImporter'

        :raises requests.RequestException: If a source download fails.
        :raises BadZipFile: If a downloaded archive is invalid.
        :raises OSError: If downloaded files cannot be written.
        """
        download_path.mkdir(parents=True, exist_ok=True)
        for theme in self.data_themes:
            try:
                response = requests.get(theme.url_route, timeout=10)
                response.raise_for_status()
                with ZipFile(io.BytesIO(response.content)) as archive:
                    base_name = theme.url_route.rsplit("/", 1)[-1].split(".")[0]
                    for file_name in archive.namelist():
                        if (
                            file_name.startswith(base_name)
                            and file_name.split(".")[-1] in ["shp", "shx", "dbf"]
                        ):
                            with archive.open(file_name, mode='r') as f, \
                                 open(f"{download_path}/{file_name}", "wb") as out_file:
                                out_file.write(f.read())
            except (requests.RequestException, BadZipFile, OSError):
                LOGGER.exception(
                    "Failed to download or extract source archive %s.",
                    theme.url_route,
                )
                raise
        return self

    def list_downloaded_files(
        self,
        download_path: Path = DEFAULT_DOWNLOAD_PATH,
        file_extension: Optional[str] = None,
    ) -> list[Path]:
        """List downloaded files, optionally filtered by extension.

        :param download_path: The directory to list files from.
        :type download_path: Path
        :param file_extension: If provided, only files with this extension.
        :type file_extension: Optional[str]
        :return: A list of paths to the downloaded files.
        :rtype: list[Path]

        :raises OSError: If the download directory cannot be read.
        """
        path = Path(download_path)
        if not path.exists():
            LOGGER.debug("Download path does not exist: %s", path)
            return []
        if file_extension:
            LOGGER.debug("Filtering downloaded files by extension: %s", file_extension)
            return list(path.glob(f"*.{file_extension}"))
        LOGGER.debug("Listing all downloaded files without filtering by extension.")
        return list(path.glob("*"))

    def clear_downloaded_files(
        self,
        download_path: Path = DEFAULT_DOWNLOAD_PATH,
        file_extension: Optional[str] = None,
    ) -> None:
        """Remove downloaded files, optionally filtered by extension.

        :param download_path: The directory to clear files from.
        :type download_path: Path
        :param file_extension: If provided, only files with this extension.
        :type file_extension: Optional[str]
        :return: None
        :rtype: None

        :raises OSError: If a downloaded file cannot be removed.
        """
        if not download_path.exists():
            LOGGER.debug("Download path does not exist: %s", download_path)
            return
        if file_extension:
            LOGGER.debug("Clearing downloaded files with extension: %s", file_extension)
            files_to_delete = download_path.glob(f"*.{file_extension}")
        else:
            LOGGER.debug("Clearing all downloaded files without filtering by extension.")
            files_to_delete = download_path.glob("*")
        for file_path in files_to_delete:
            if file_path.is_file():
                LOGGER.debug("Deleting file: %s", file_path)
                file_path.unlink()
