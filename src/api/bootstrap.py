"""Initialisation de la base de données avant le démarrage de l'API."""

from .config import DatabaseSettings
from .config.c_databases import DatabaseConfig
from .common.datas import DataImporter


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
    for file in files_list:
        pass

def main() -> None:
    """Initialise la base de données avant le démarrage de l'API."""
    create_database()
    import_datas()


if __name__ == "__main__":
    main()
