"""
Common data structures and utilities for the API.
"""
from __future__ import annotations

from enum import Enum
import tomllib
from dataclasses import dataclass
from zipfile import ZipFile
import io

import requests

class DataFamily(Enum):
    """Enumeration of possible data families."""
    CULTURAL = "cultural"
    PHYSICAL = "physical"
    RASTER = "raster"

class Precision(Enum):
    """Enumeration of possible precision levels for vector data."""
    LOW = 110
    MEDIUM = 50
    HIGH = 10

PRECISION_MAP = {
    "low": Precision.LOW,
    "medium": Precision.MEDIUM,
    "high": Precision.HIGH,
}

@dataclass(frozen=True)
class DataTheme:
    """Data structure representing a data theme."""
    name: str
    precisions: int
    url_route: str

class DataImporter:
    """Class responsible for importing data themes.
    
    args:
        file_path (str): Path to the TOML file containing data theme definitions.
    
    eg:
        di = DataImporter()
        url = di.data_themes[0].url_route if di.data_themes else None
        >>> https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip
    """
    def __init__(self, file_path: str = "/etc/app/zones.toml") -> None:
        with open(file_path, "rb") as _f:
            f = tomllib.load(_f)
        self.url_base = f["source_path"]
        self.data_themes: list[DataTheme] = []
        zones = f["data_family"]
        self.append_data_theme(list(zones.get("cultural", [])), "cultural")
        self.append_data_theme(list(zones.get("physical", [])), "physical")
        self.append_data_theme(list(zones.get("raster", [])), "raster")

    def append_data_theme(self, zone_list: list[dict[str, str]], zone_name: str) -> None:
        """Append data themes from a given list of zones and their associated zone name."""
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

    def download_files(self) -> None:
        """Download all data files for the imported data themes."""
        for theme in self.data_themes:
            response = requests.get(theme.url_route, timeout=10)
            response.raise_for_status()
            if response.status_code == 200:
                archive = ZipFile(io.BytesIO(response.content))
                base_name = theme.url_route.rsplit("/", 1)[-1].split(".")[0]
                for file_name in archive.namelist():
                    if (
                        file_name.startswith(base_name)
                        and file_name.split(".")[-1] in ["shp", "shx", "dbf"]
                    ):
                        with (archive.open(file_name, mode='r') as f,
                              open(file_name, "wb") as out_file
                        ):
                            out_file.write(f.read())
            else:
                print(
                    f"Failed to download {theme.url_route}, "
                    f"status code: {response.status_code}"
                )
