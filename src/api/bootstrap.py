"""Module of initial initialization of the database before the API starts.

.. functions::
    - `create_database`: Creates the missing database objects.
    - `import_datas`: Imports the initial data into the database.
    - `main`: Initializes the database before the API starts.
   
.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

import sys

from auth.manager import AuthManager
from .config import DatabaseSettings, FlaskSettings
from .config.c_databases import DatabaseConfig
from .common.datas import DataImporter, DataInjecter


def create_database() -> None:
    """Creates the missing database objects.

    :return: None
    :rtype: None
    """
    database = DatabaseConfig(DatabaseSettings())
    try:
        database.initialize()
        AuthManager.initialize_database(database.session, FlaskSettings())
    finally:
        database.session.remove()
        database.engine.dispose()

def import_datas() -> None:
    """Imports the initial data into the database.

    :return: None
    :rtype: None
    """
    data_importer = DataImporter()
    files_list = data_importer.download_files().list_downloaded_files()
    data_injecter = DataInjecter(files_list)
    data_injecter.inject_geo_zones()
    data_importer.clear_downloaded_files()

def main() -> None:
    """Initializes the database before the API starts.

    :return: None
    :rtype: None
    """
    sys.stdout.write("Initialisation de la base de données...\n")
    sys.stdout.flush()
    create_database()
    sys.stdout.write("Base de données initialisée.\n")
    sys.stdout.flush()
    sys.stdout.write("Importation des données initiales...\n")
    sys.stdout.flush()
    import_datas()
    sys.stdout.write("Données initiales importées.\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
