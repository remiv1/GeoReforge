"""Initialization for the database objects package.

.. classes::
    - `Base`: base class for all database objects.

.. constantes::
    - `TABLE_ARGS`: default table arguments for the database objects.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0
"""
from __future__ import annotations

from typing import Any
import logging

from sqlalchemy.orm import DeclarativeBase

from ...config import DatabaseSettings
from ...config.c_databases import DbType

settings = DatabaseSettings()

TABLE_ARGS = {"schema": settings.DB_SCHEMA} if settings.DB_TYPE == DbType.POSTGRESQL else {}
LOGGER = logging.getLogger(__name__)

class Base(DeclarativeBase):
    """Base class for all database objects.
    
    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """

    def to_dict(self) -> dict[str, Any]:
        """Converts the database object to a dictionary.
        
        :returns: The database object as a dictionary.
        :rtype: dict[str, Any]
        """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Any:
        """Creates a database object from a dictionary.

        :param data: The dictionary containing the database object data.
        :type data: dict[str, Any]
        :returns: The created database object.
        :rtype: Any

        .. note::
            This method assumes that the keys in the dictionary match the attribute names
            of the database object. Extra keys in the dictionary will be ignored.
        
        .. example::
            ```python
            data = response.to_json()
            obj = MyDatabaseObject.from_dict(data)
            ```
        """
        obj = cls()
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
            else:
                LOGGER.debug("Unknown attribute '%s' in data dictionary", key)
        return obj
