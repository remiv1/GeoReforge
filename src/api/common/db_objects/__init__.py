"""Initialization for the database objects package."""

from sqlalchemy.orm import DeclarativeBase

from api.config import DatabaseSettings
from api.config.c_databases import DbType

settings = DatabaseSettings()

TABLE_ARGS = {"schema": settings.DB_SCHEMA} if settings.DB_TYPE == DbType.POSTGRESQL else {}

class Base(DeclarativeBase):    # pylint: disable=R0903
    """Base class for all database objects."""
    pass    # pylint: disable=W0107
