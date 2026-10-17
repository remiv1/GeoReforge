"""Initialize the database and import initial geographic sources.

.. functions::
    - `create_database`: Creates the missing database objects.
    - `import_datas`: Imports the initial data into the database.
    - `main`: Initializes the database before the API starts.
   
.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

import logging
import sys

from auth.manager import AuthManager
from .config import DatabaseSettings, FlaskSettings
from .config.c_databases import DatabaseConfig
from .common.datas import DataImporter, DataInjecter

LOGGER = logging.getLogger(__name__)


def create_database() -> None:
    """Create missing database objects and initialize authentication data.

    :return: None
    :rtype: None

    :raises SQLAlchemyError: If database or authentication initialization fails.
    """
    database: DatabaseConfig | None = None
    try:
        database = DatabaseConfig(DatabaseSettings())
        database.initialize()
        AuthManager.initialize_database(database.session, FlaskSettings())
    except Exception:
        LOGGER.exception("Database initialization failed.")
        raise
    finally:
        if database is not None:
            database.session.remove()
            database.engine.dispose()

def import_datas() -> None:
    """Download and import configured geographic source data.

    :return: None
    :rtype: None

    :raises Exception: If a source download or import fails.
    """
    try:
        data_importer = DataImporter()
        files_list = data_importer.download_files().list_downloaded_files()
        data_injecter = DataInjecter(files_list, data_importer.data_themes)
        data_injecter.inject_geo_zones()
        data_importer.clear_downloaded_files()
    except Exception:
        LOGGER.exception("Initial geographic source import failed.")
        raise

def main() -> None:
    """Initialize the database before the API starts.

    :return: None
    :rtype: None

    :raises Exception: If database setup or initial source import fails.
    """
    sys.stdout.write("Initializing database...\n")
    sys.stdout.flush()
    create_database()
    sys.stdout.write("Database initialized.\n")
    sys.stdout.flush()
    sys.stdout.write("Importing initial geographic data...\n")
    sys.stdout.flush()
    import_datas()
    sys.stdout.write("Initial geographic data imported.\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
