"""Database configuration for the GeoReforge API."""

from enum import Enum
from typing import Any
import sqlite3
from sqlalchemy import create_engine, event, Engine, URL, text
from sqlalchemy.schema import CreateSchema
from sqlalchemy.orm import scoped_session, sessionmaker

from pydantic import computed_field, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DbType(str, Enum):
    """Enumeration of supported database types."""
    SQLITE = "sqlite"
    POSTGRESQL = "postgres"
    MYSQL = "mysql"
    MARIADB = "mariadb"


class Settings(BaseSettings):
    """Database settings for the GeoReforge API."""
    model_config = SettingsConfigDict(
        env_file = "/etc/app/env.conf",
        extra = "ignore",
    )

    EXTERNAL_DB: bool = False
    DB_PATH: str = "/var/lib/app/database.db"
    DB_TYPE: DbType = DbType.SQLITE

    DB_HOST: str = "localhost"
    DB_PORT: int = Field(default=0, ge=0, le=65535)

    DB_USER: str = ""
    DB_PASSWORD: str = ""

    DB_NAME: str = "appdb"
    DB_SCHEMA: str = "public"

    @computed_field
    @property
    def db_url(self) -> str | URL:
        """Construct the database URL from the individual components."""
        if not self.EXTERNAL_DB and self.DB_TYPE != DbType.SQLITE:
            raise ValueError(f"If not external, DB_TYPE have to be {DbType.SQLITE}")
        if not self.EXTERNAL_DB or self.DB_TYPE == DbType.SQLITE:
            return f"sqlite:///{self.DB_PATH}"
        url_param: dict[str, Any] = {
            "username": self.DB_USER,
            "password": self.DB_PASSWORD,
            "host": self.DB_HOST,
            "port": self.DB_PORT,
            "database": self.DB_NAME,
        }
        if self.DB_TYPE == DbType.POSTGRESQL:
            url_base = URL.create(
                drivername="postgresql+psycopg2",
                **url_param,
            )
            return url_base
        if self.DB_TYPE == DbType.MYSQL:
            url_base = URL.create(
                drivername="mysql+pymysql",
                **url_param,
            )
            return url_base
        if self.DB_TYPE == DbType.MARIADB:
            return URL.create(drivername="mariadb+pymysql", **url_param)
        raise ValueError(f"Unsupported DB_TYPE for external database: {self.DB_TYPE}")

    @model_validator(mode="after")
    def validate_database_config(self):
        """Validate the database configuration after model initialization."""
        if not self.EXTERNAL_DB and self.DB_TYPE != DbType.SQLITE:
            raise ValueError(f"If not external, DB_TYPE have to be {DbType.SQLITE}")
        return self


class DatabaseConfig:   # pylint: disable=R0903
    """Class representing the database configuration."""
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = self._create_engine()
        self.session = scoped_session(
            sessionmaker(
                bind=self.engine,
                autoflush=False,
                expire_on_commit=False,
            ),
        )

    def initialize(self) -> None:
        """Initialise les prérequis spatiaux et les tables manquantes."""
        from api.common.db_objects.geo_zones import GeographicZone  # pylint: disable=C0415

        with self.engine.begin() as connection:
            if self.settings.DB_TYPE == DbType.POSTGRESQL:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
                connection.execute(CreateSchema(self.settings.DB_SCHEMA, if_not_exists=True))
            GeographicZone.metadata.create_all(connection, checkfirst=True)

    def _create_engine(self):
        """
        Create the SQLAlchemy engine separating the configuration between SQLite
        and external databases.
        """
        engine = create_engine(self.settings.db_url)

        if self.settings.DB_TYPE == DbType.SQLITE:
            self._configure_sqlite(engine)
        elif self.settings.DB_TYPE == DbType.POSTGRESQL:
            self._configure_postgresql(engine)
        elif self.settings.DB_TYPE in {DbType.MYSQL, DbType.MARIADB}:
            self._configure_mysql(engine)

        return engine

    def _configure_sqlite(self, engine: Engine):
        """Configure SQLite-specific settings for the SQLAlchemy engine."""
        @event.listens_for(engine, "connect")
        def load_spatialite(dbapi_connection: sqlite3.Connection, _connection_record: Any):
            dbapi_connection.enable_load_extension(True)
            try:
                dbapi_connection.load_extension("mod_spatialite")
            finally:
                dbapi_connection.enable_load_extension(False)
            if not dbapi_connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'spatial_ref_sys'"
            ).fetchone():
                dbapi_connection.execute("SELECT InitSpatialMetaData(1)")

    def _configure_postgresql(self, engine: Engine):
        """Configure PostgreSQL-specific settings for the SQLAlchemy engine."""

    def _configure_mysql(self, engine: Engine):
        """Configure MySQL-specific settings for the SQLAlchemy engine."""
