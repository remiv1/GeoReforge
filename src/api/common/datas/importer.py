"""
Common data structures and utilities for the API.

.. class:: `DataImporter` class responsible for importing data themes.
"""
from __future__ import annotations

import tomllib
from zipfile import ZipFile
import io
from pathlib import Path
from typing import Optional

import requests

from ..other_objects import Precision, PRECISION_MAP, DataTheme

DEFAULT_DOWNLOAD_PATH = Path("/tmp/app/")

class DataImporter:
    """Class responsible for importing data themes.
    
    :param file_path: Path to the TOML file containing data theme definitions.
    :type file_path: str

    .. Example::
        .. code-block:: python
            di = DataImporter()
            url = di.data_themes[0].url_route if di.data_themes else None
            >>> https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip

    .. Note::
        Ensure that the TOML file follows the expected structure for data themes.
    
    .. moduleauthor:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    def __init__(self, file_path: str = "/etc/app/zones.toml") -> None:
        with open(file_path, "rb") as _f:
            f = tomllib.load(_f)
        self.url_base = f["source_path"]
        self.data_themes: list[DataTheme] = []
        zones = f["data_family"]
        self._append_data_theme(list(zones.get("cultural", [])), "cultural")
        self._append_data_theme(list(zones.get("physical", [])), "physical")
        self._append_data_theme(list(zones.get("raster", [])), "raster")

    def _append_data_theme(self, zone_list: list[dict[str, str]], zone_name: str) -> None:
        """
        Append data themes from a given list of zones and their associated zone name

        :param zone_list: List of zones with their details.
        :type zone_list: list[dict[str, str]]
        :param zone_name: The name of the zone category (e.g., "cultural", "physical", "raster").
        **`Use the DataFamily class enumeration for valid zone categories.`**
        :returns: None
        :rtype: None
        :type zone_name: str
        """
        for dt in zone_list:
            for p in dt.get("precision", ["high"]):
                p = PRECISION_MAP.get(p, Precision.HIGH).value
                route = (
                    f'{self.url_base}/{p}m_{zone_name}/ne_{p}m_{dt.get("link", "")}.zip'
                )
                self.data_themes.append(
                    DataTheme(
                        name=dt["name"],
                        precisions=p,
                        url_route=route
                    )
                )

    def download_files(self, download_path: Path = DEFAULT_DOWNLOAD_PATH) -> 'DataImporter':
        """
        Download all data files for the imported data themes.

        :param download_path: The directory to download files to.
        :type download_path: Path
        :returns: The instance of the `DataImporter` after downloading files.
        :rtype: 'DataImporter'
        """
        download_path.mkdir(parents=True, exist_ok=True)
        for theme in self.data_themes:
            response = requests.get(theme.url_route, timeout=10)
            response.raise_for_status()
            if response.status_code == 200:
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
            else:
                print(
                    f"Failed to download {theme.url_route}, "
                    f"status code: {response.status_code}"
                )
        return self

    def list_downloaded_files(
        self,
        download_path: Path = DEFAULT_DOWNLOAD_PATH,
        file_extension: Optional[str] = None,
    ) -> list[Path]:
        """
        List all downloaded files in the specified directory,
        optionally filtering by file extension.

        :param download_path: The directory to list files from.
        :type download_path: Path
        :param file_extension: If provided, only files with this extension.
        :type file_extension: Optional[str]
        :return: A list of paths to the downloaded files.
        :rtype: list[Path]
        """
        path = Path(download_path)
        if not path.exists():
            return []
        if file_extension:
            return list(path.glob(f"*.{file_extension}"))
        return list(path.glob("*"))

    def clear_downloaded_files(
        self,
        download_path: Path = DEFAULT_DOWNLOAD_PATH,
        file_extension: Optional[str] = None,
    ) -> None:
        """
        Clear all downloaded files in the specified directory,
        optionally filtering by file extension.

        :param download_path: The directory to clear files from.
        :type download_path: Path
        :param file_extension: If provided, only files with this extension.
        :type file_extension: Optional[str]
        :return: None
        :rtype: None
        """
        if not download_path.exists():
            return
        if file_extension:
            files_to_delete = download_path.glob(f"*.{file_extension}")
        else:
            files_to_delete = download_path.glob("*")
        for file_path in files_to_delete:
            if file_path.is_file():
                file_path.unlink()
