"""Initialisation de la base de données avant le démarrage de l'API."""

import sys
from .config import DatabaseSettings
from .config.c_databases import DatabaseConfig
from .common.datas import DataImporter, DataInjecter


def create_database() -> None:
    """Crée les objets de base de données manquants."""
    database = DatabaseConfig(DatabaseSettings())
    try:
        database.initialize()
    finally:
        database.session.remove()
        database.engine.dispose()

def import_datas() -> None:
    """Importe les données initiales dans la base de données."""
    data_importer = DataImporter()
    files_list = data_importer.download_files().list_downloaded_files()
    data_injecter = DataInjecter(files_list)
    data_injecter.inject_geo_zones()
    data_importer.clear_downloaded_files()

def main() -> None:
    """Initialise la base de données avant le démarrage de l'API."""
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
