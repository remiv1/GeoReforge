"""
Module to map data between `zones.toml` and the database.
"""

import tomllib
from typing import Optional

FILE_PATH = "/etc/app/zones.toml"

class ZonesMapper:
    """
    Class responsible for mapping data between `zones.toml` and the database.
    """

    def __init__(self, file_path: str = FILE_PATH):
        """Initializes the ZonesMapper with the given TOML file path."""
        self.file_path = file_path
        __loaded_datas = self.load_file()
        __families = __loaded_datas.get("data_family", {})
        self.physical = __families.get("physical", [])
        self.cultural = __families.get("cultural", [])
        self.raster = __families.get("raster", [])
        self.mapping = __families.get("mapping", {})
        self.__key = None
        self.__classes = None

    def load_file(self):
        """Loads zones from the TOML file."""
        with open(self.file_path, "rb") as f:
            return tomllib.load(f)

    def get_mapper(self, key: Optional[str] = None) -> dict[str, str]:
        """Retrieves the mapping for the given key."""
        self.__key = key if key is not None else self.__key
        self.__classes = self.mapping.get(self.__key, {}).get("classes", {})
        mapper = self.mapping.get(self.__key, {}).copy()
        mapper.pop("classes", None)
        return mapper

    def get_classes(self) -> dict[str, str]:
        """Retrieves the classes for the last accessed key."""
        return self.__classes if self.__classes is not None else {}
