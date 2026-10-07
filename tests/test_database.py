"""Vérification de l'initialisation des bases géospatiales."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError


SOURCE = Path(__file__).resolve().parents[1] / "src"
WKT = "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)))"


def bootstrap(**variables: str) -> subprocess.CompletedProcess[str]:
    """Exécute le bootstrap dans un processus isolé avec ses propres réglages."""
    environment = os.environ.copy()
    environment.update(variables)
    environment["PYTHONPATH"] = str(SOURCE)
    return subprocess.run(
        [sys.executable, "-m", "api.bootstrap"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_sqlite_first_start_and_restart(tmp_path: Path) -> None:
    """Crée la table spatiale puis conserve une zone après redémarrage."""
    database_path = tmp_path / "zones.db"
    variables = {"EXTERNAL_DB": "false", "DB_TYPE": "sqlite", "DB_PATH": str(database_path)}
    first = bootstrap(**variables)
    assert first.returncode == 0, first.stderr

    with sqlite3.connect(database_path) as connection:
        connection.enable_load_extension(True)
        try:
            connection.load_extension("mod_spatialite")
        finally:
            connection.enable_load_extension(False)
        connection.execute(
            "INSERT INTO geo_zones (kind, code, name, boundary) "
            "VALUES (?, ?, ?, GeomFromText(?, 4326))",
            ("test", "example", "Example", WKT),
        )
        connection.commit()

    second = bootstrap(**variables)
    assert second.returncode == 0, second.stderr
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM geo_zones WHERE code = ?", ("example",)
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM spatial_ref_sys WHERE srid = 4326"
        ).fetchone() == (1,)


def test_missing_sqlite_directory_prevents_start(tmp_path: Path) -> None:
    """Échoue si la base n'est pas accessible, sans créer de répertoire."""
    database_path = tmp_path / "absent" / "zones.db"
    result = bootstrap(EXTERNAL_DB="false", DB_TYPE="sqlite", DB_PATH=str(database_path))
    assert result.returncode != 0
    assert not database_path.parent.exists()


@pytest.mark.parametrize(
    ("database_type", "url_variable"),
    [
        ("postgres", "TEST_POSTGRES_URL"),
        ("mysql", "TEST_MYSQL_URL"),
        ("mariadb", "TEST_MARIADB_URL"),
    ],
)
def test_external_first_start_and_restart(database_type: str, url_variable: str) -> None:
    """Prépare une base de test isolée et conserve une géométrie au redémarrage."""
    if url_variable not in os.environ:
        pytest.skip(f"{url_variable} non défini : conteneur de test non démarré")

    url = make_url(os.environ[url_variable])
    schema = "georeforge_bootstrap_test" if database_type == "postgres" else None
    variables = {
        "EXTERNAL_DB": "true",
        "DB_TYPE": database_type,
        "DB_HOST": url.host or "localhost",
        "DB_PORT": str(url.port or 0),
        "DB_USER": url.username or "",
        "DB_PASSWORD": url.password or "",
        "DB_NAME": url.database or "",
        "DB_SCHEMA": schema or "public",
    }

    engine = create_engine(url, connect_args={"connect_timeout": 3})
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                with engine.connect():
                    break
            except OperationalError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)

        first = bootstrap(**variables)
        assert first.returncode == 0, first.stderr

        assert inspect(engine).has_table("geo_zones", schema=schema)
        table_name = "georeforge_bootstrap_test.geo_zones" if schema else "geo_zones"
        zone_code = uuid4().hex
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"INSERT INTO {table_name} (kind, code, name, boundary) "
                    "VALUES (:kind, :code, :name, ST_GeomFromText(:geometry, 4326))"
                ),
                {"kind": "test", "code": zone_code, "name": "Example", "geometry": WKT},
            )

        second = bootstrap(**variables)
        assert second.returncode == 0, second.stderr
        with engine.connect() as connection:
            assert connection.execute(
                text(f"SELECT ST_SRID(boundary) FROM {table_name} WHERE code = :code"),
                {"code": zone_code},
            ).scalar_one() == 4326
            if database_type == "postgres":
                assert connection.execute(
                    text("SELECT count(*) FROM pg_extension WHERE extname = 'postgis'")
                ).scalar_one() == 1
    finally:
        engine.dispose()
