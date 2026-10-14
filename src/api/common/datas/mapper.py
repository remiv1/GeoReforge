"""
Module to map data between `zones.toml` and the database.

.. class::
    - `ZonesMapper`: class responsible for mapping data between `zones.toml` and the database.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0
"""
from __future__ import annotations

import tomllib
import logging

from typing import Optional, Any

FILE_PATH = "/etc/app/zones.toml"
LOGGER = logging.getLogger(__name__)

class ZonesMapper:
    """Class responsible for mapping data between `zones.toml` and the database.

    :param file_path: Path to the TOML file containing zone definitions.
    :type file_path: str

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """

    def __init__(self, file_path: str = FILE_PATH):
        """Initializes the ZonesMapper with the given TOML file path.
        
        :param file_path: Path to the TOML file containing zone definitions.
        :type file_path: str
        """
        self.file_path = file_path
        __loaded_datas = self.load_file()
        __families = __loaded_datas.get("data_family", {})
        self.physical = __families.get("physical", [])
        self.cultural = __families.get("cultural", [])
        self.raster = __families.get("raster", [])
        self.mapping = __families.get("mapping", {})
        self.__key = None
        self.__classes = None

    def load_file(self) -> dict[str, Any]:
        """Loads zones from the TOML file.

        :returns: The loaded TOML data as a dictionary.
        :rtype: dict
        """
        try:
            with open(self.file_path, "rb") as f:
                return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            LOGGER.exception("Failed to load TOML file: %s", e)
            return {}

    def get_mapper(self, key: Optional[str] = None) -> dict[str, str]:
        """Retrieves the mapping for the given key.
        
        :param key: The key for which to retrieve the mapping. If None, uses the last accessed key.
        :type key: Optional[str]
        :returns: The mapping dictionary for the given key.
        :rtype: dict[str, str]
        """
        self.__key = key if key is not None else self.__key
        self.__classes = self.mapping.get(self.__key, {}).get("classes", {})
        mapper = self.mapping.get(self.__key, {}).copy()
        mapper.pop("classes", None)
        return mapper

    def get_classes(self) -> dict[str, str]:
        """Retrieves the classes for the last accessed key.

        :returns: The classes dictionary for the last accessed key.
        :rtype: dict[str, str]
        """
        return self.__classes if self.__classes is not None else {}
