"""Tests du mapping, de l'import et de l'injection des zones."""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import time
from uuid import uuid4
import zipfile

import pytest
import shapefile
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from api.common.datas import injecter as injecter_module
from api.common.datas import importer as importer_module
from api.common.datas.injecter import AgregateZone, DataInjecter
from api.common.datas.importer import DataImporter
from api.common.datas.mapper import ZonesMapper
from api.common.db_objects.geo_zones import GeographicZone
from api.common.repositories import common as common_repo_module
from api.config import DatabaseConfig, DatabaseSettings


ZONES_CONFIG = Path(__file__).parent / "fixtures" / "zones.toml"
COUNTRY = {
    "NAME_LONG": "Testland",
    "ISO_A3": "TST",
    "featurecla": "Admin-0 country",
}
LAKE = {
    "name_en": "Test Lake",
    "ne_id": "lake-1",
    "featurecla": "Lake",
}
RING = [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]


def shapefile_parts(properties: dict[str, str]) -> dict[str, bytes]:
    """Crée les trois composants d'un shapefile polygonal en mémoire."""
    shp = BytesIO()
    shx = BytesIO()
    dbf = BytesIO()
    writer = shapefile.Writer(
        shp=shp,    # type: ignore
        shx=shx,    # type: ignore
        dbf=dbf,    # type: ignore
        shapeType=shapefile.POLYGON,
    )
    for field_name in properties:
        writer.field(field_name, "C")    # type: ignore
    writer.poly([RING])    # type: ignore
    writer.record(*properties.values())
    writer.close()
    return {".shp": shp.getvalue(), ".shx": shx.getvalue(), ".dbf": dbf.getvalue()}


def shapefile_archive(link: str, properties: dict[str, str]) -> bytes:
    """Emballe un shapefile en mémoire sous le nom Natural Earth attendu."""
    base_name = f"ne_10m_{link}"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for extension, content in shapefile_parts(properties).items():
            archive.writestr(f"{base_name}{extension}", content)
        archive.writestr(f"{base_name}.prj", b"ignored projection")
        archive.writestr("unrelated.shp", b"ignored shapefile")
    return buffer.getvalue()


class FakeResponse:
    """Réponse HTTP minimale pour les téléchargements simulés."""

    status_code = 200

    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        """Ne fait rien, lève une exception si le statut HTTP est incorrect."""
        return None


class FakeRepository:
    """Dépôt de test qui conserve les zones préparées par l'injecteur."""

    def __init__(self) -> None:
        self.zones: list[GeographicZone] = []
        self.commit_count = 0

    def add_geo_zone(self, zone: GeographicZone, commit: bool = True) -> GeographicZone:
        """Ajoute une zone géographique au dépôt factice sans effectuer de commit."""
        assert not commit
        self.zones.append(zone)
        return zone

    def commit(self) -> bool:
        """Effectue un commit factice en incrémentant le compteur de commits."""
        self.commit_count += 1
        return True


def aggregate(source_name: str, properties: dict[str, str]) -> AgregateZone:
    """Construit un agrégat à partir d'un enregistrement shapefile synthétique."""
    parts = shapefile_parts(properties)
    return AgregateZone(
        source_name=source_name,
        shp=BytesIO(parts[".shp"]),
        shx=BytesIO(parts[".shx"]),
        dbf=BytesIO(parts[".dbf"]),
    )


def wait_for_database(database: DatabaseConfig) -> None:
    """Attend au plus 60 secondes qu'une base externe accepte une connexion."""
    deadline = time.monotonic() + 60
    while True:
        try:
            with database.engine.connect():
                return
        except OperationalError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


def test_mapper_loads_fields_and_classes_for_each_key() -> None:
    """Teste que le mapper charge correctement les champs et les classes pour chaque clé."""
    mapper = ZonesMapper(str(ZONES_CONFIG))

    assert mapper.get_mapper("admin_0_countries") == {
        "name": "NAME_LONG",
        "code": "ISO_A3",
        "geometry": "geometry",
        "class": "featurecla",
    }
    assert mapper.get_classes() == {"Admin-0 country": "Pays"}

    assert mapper.get_mapper("lakes") == {
        "name": "name_en",
        "code": "ne_id",
        "geometry": "geometry",
        "class": "featurecla",
    }
    assert mapper.get_classes() == {"Lake": "Lac"}


def test_importer_builds_routes_and_extracts_shapefile_components(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the DataImporter correctly builds routes and extracts shapefile components."""
    importer = DataImporter(str(ZONES_CONFIG))
    requests: list[str] = []

    def fake_get(url: str, timeout: int) -> FakeResponse:
        assert timeout == 10
        requests.append(url)
        if "admin_0_countries" in url:
            return FakeResponse(shapefile_archive("admin_0_countries", COUNTRY))
        return FakeResponse(shapefile_archive("lakes", LAKE))

    monkeypatch.setattr(importer_module.requests, "get", fake_get)

    assert [theme.url_route for theme in importer.data_themes] == [
        "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_countries.zip",
        "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_lakes.zip",
    ]
    files = importer.download_files(tmp_path).list_downloaded_files(tmp_path)

    assert set(requests) == {theme.url_route for theme in importer.data_themes}
    assert {path.name for path in files} == {
        "ne_10m_admin_0_countries.shp",
        "ne_10m_admin_0_countries.shx",
        "ne_10m_admin_0_countries.dbf",
        "ne_10m_lakes.shp",
        "ne_10m_lakes.shx",
        "ne_10m_lakes.dbf",
    }


def test_build_aggregates_keeps_source_name_and_ignores_incomplete_groups(
    tmp_path: Path,
) -> None:
    """Test that the DataInjecter correctly builds aggregate zones and ignores incomplete groups."""
    paths: list[Path] = []
    for extension in (".shp", ".shx", ".dbf"):
        path = tmp_path / f"ne_10m_lakes{extension}"
        path.write_bytes(extension.encode())
        paths.append(path)
    for extension in (".shp", ".dbf"):
        path = tmp_path / f"ne_10m_incomplete{extension}"
        path.write_bytes(extension.encode())
        paths.append(path)

    data_injecter = DataInjecter.__new__(DataInjecter)
    data_injecter.path_list = paths

    aggregates = data_injecter._build_aggregates()  # type: ignore # pylint: disable=W0212

    assert len(aggregates) == 1
    assert aggregates[0].source_name == "ne_10m_lakes"
    assert aggregates[0].shp.getvalue() == b".shp"


def test_injecter_selects_each_mapping_and_translates_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the DataInjecter selects each mapping and translates classes correctly."""
    monkeypatch.setattr(
        injecter_module,
        "ZonesMapper",
        lambda: ZonesMapper(str(ZONES_CONFIG)),
    )
    repository = FakeRepository()
    data_injecter = DataInjecter.__new__(DataInjecter)
    data_injecter.repo = repository    # type: ignore

    data_injecter.inject_geo_zones()

    assert [(zone.kind, zone.code, zone.name) for zone in repository.zones] == [
        ("Pays", "TST", "Testland"),
        ("Lac", "lake-1", "Test Lake"),
    ]
    assert all(isinstance(zone.boundary, WKTElement) for zone in repository.zones)
    assert all(zone.boundary.srid == 4326 for zone in repository.zones)
    assert repository.commit_count == 1


def test_injecter_rejects_unknown_mapping_and_missing_source_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the DataInjecter raises errors for unknown mappings and missing source classes."""
    monkeypatch.setattr(
        injecter_module,
        "ZonesMapper",
        lambda: ZonesMapper(str(ZONES_CONFIG)),
    )
    repository = FakeRepository()
    data_injecter = DataInjecter.__new__(DataInjecter)
    data_injecter.repo = repository    # type: ignore

    with pytest.raises(ValueError, match="Aucun mapping trouvé"):
        data_injecter.inject_geo_zones()

    with pytest.raises(ValueError, match="Classe source absente"):
        data_injecter.inject_geo_zones()
    assert repository.commit_count == 0


@pytest.mark.parametrize(
    ("database_type", "url_variable"),
    [
        pytest.param("sqlite", None, id="sqlite"),
        pytest.param("postgres", "TEST_POSTGRES_URL", id="postgres"),
        pytest.param("mysql", "TEST_MYSQL_URL", id="mysql"),
        pytest.param("mariadb", "TEST_MARIADB_URL", id="mariadb"),
    ],
)
def test_full_injection_persists_zones(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    database_type: str,
    url_variable: str | None,
) -> None:
    """Vérifie que l’injection complète persiste les zones dans chaque moteur configuré."""
    if database_type == "sqlite":
        settings = DatabaseSettings(
            EXTERNAL_DB=False,
            DB_TYPE="sqlite",    # type: ignore
            DB_PATH=str(tmp_path / "zones.db"),
        )
    else:
        if url_variable is None or url_variable not in os.environ:
            pytest.skip(f"{url_variable} non défini : base de test non démarrée")
        url = make_url(os.environ[url_variable])
        settings = DatabaseSettings(
            EXTERNAL_DB=True,
            DB_TYPE=database_type,    # type: ignore
            DB_HOST=url.host or "localhost",
            DB_PORT=url.port or 0,
            DB_USER=url.username or "",
            DB_PASSWORD=url.password or "",
            DB_NAME=url.database or "",
        )
    database = DatabaseConfig(settings)
    try:
        if database_type != "sqlite":
            wait_for_database(database)
        database.initialize()
    except OperationalError as error:
        database.engine.dispose()
        if "mod_spatialite" in str(error).lower():
            pytest.skip("L'extension mod_spatialite n'est pas installée")
        raise

    monkeypatch.setattr(injecter_module, "DatabaseSettings", lambda: settings)
    monkeypatch.setattr(
        injecter_module,
        "DatabaseConfig",
        lambda _settings: database,    # type: ignore
    )
    monkeypatch.setattr(common_repo_module, "DatabaseSettings", lambda: settings)
    monkeypatch.setattr(
        common_repo_module,
        "DatabaseConfig",
        lambda _settings: database,    # type: ignore
    )
    monkeypatch.setattr(
        injecter_module,
        "ZonesMapper",
        lambda: ZonesMapper(str(ZONES_CONFIG)),
    )
    run_id = uuid4().hex
    country_properties = {**COUNTRY, "ISO_A3": f"T{run_id}"}
    lake_properties = {**LAKE, "ne_id": f"L{run_id}"}

    def fake_get(url: str, timeout: int) -> FakeResponse:
        del timeout
        if "admin_0_countries" in url:
            return FakeResponse(shapefile_archive("admin_0_countries", country_properties))
        return FakeResponse(shapefile_archive("lakes", lake_properties))

    monkeypatch.setattr(importer_module.requests, "get", fake_get)

    try:
        downloaded_files = DataImporter(str(ZONES_CONFIG)).download_files(tmp_path)
        data_injecter = DataInjecter(downloaded_files.list_downloaded_files(tmp_path))
        data_injecter._build_aggregates() # type: ignore # pylint: disable=W0212
        data_injecter.inject_geo_zones()

        rows = database.session.execute(
            select(GeographicZone.kind, GeographicZone.code, GeographicZone.name).where(
                GeographicZone.code.in_([country_properties["ISO_A3"], lake_properties["ne_id"]])
            )
        ).all()
        assert {(row.kind, row.code, row.name) for row in rows} == {
            ("Pays", country_properties["ISO_A3"], "Testland"),
            ("Lac", lake_properties["ne_id"], "Test Lake"),
        }
    finally:
        database.session.remove()
        database.engine.dispose()
