"""Tests des droits et des parcours de l'interface sur une base jetable."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch
from html.parser import HTMLParser

from flask import Flask, g, request
from flask.testing import FlaskClient
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, box
from sqlalchemy import select
from sqlalchemy.sql.functions import count
import pytest

from api.common.db_objects.geo_forged import GeoForged, GeoForgedItem
from api.common.db_objects.geo_zones import GeographicZone
from api.common.db_objects.users import UserPreferences
from api.config import DatabaseConfig, DatabaseSettings, FlaskSettings
from api.main import create_app
from auth.services import UserService


@pytest.fixture(name="front")
def front_fixture(tmp_path: Path) -> Iterator[tuple[Flask, DatabaseConfig, FlaskClient]]:
    """Fournit une application et des sources dans une base SpatiaLite isolee."""
    database = DatabaseConfig(DatabaseSettings(DB_PATH=str(tmp_path / "front.db")))
    database.initialize()
    users = UserService(database.session)
    users.ensure_groups()
    identities = {
        role: users.create_user(
            role.lower(), f"{role.lower()}@example.test", "test-password", [role]
        )
        for role in ("VIEWER", "EDITOR", "ADMIN")
    }
    for name, code, bounds in [
        ("France", "FR", (0, 0, 3, 3)),
        ("Paris", "PAR", (1, 1, 2, 2)),
        ("Belgique", "BE", (3, 1, 4, 2))
    ]:
        database.session.add(
            GeographicZone(
                name=name,
                code=code,
                kind="Test",
                boundary=from_shape(MultiPolygon([box(*bounds)]), srid=4326)
            )
        )
    database.session.commit()
    app = create_app(
        FlaskSettings(
            AUTH_MODE="none",
            FLASK_ENV="development",
            SECRET_KEY="front-only-secret-key-for-isolated-tests"
        ),
        database,
    )
    app.testing = True

    @app.before_request
    def test_identity() -> None:
        role = request.headers.get("X-Test-Role", "ADMIN")
        g.setdefault("auth_user", identities.get(role))

    with app.test_client() as client:
        yield app, database, client
    database.session.remove()
    database.engine.dispose()


def _post(client: FlaskClient, path: str, data: Any, role: str = "ADMIN") -> Any:
    token = client.get("/auth/csrf").json["csrf_token"] # type: ignore
    return client.post(
        path,
        data=data,
        headers={
            "X-CSRFToken": token,
            "X-Test-Role": role,
            "HX-Request": "true",
        },
    )


def _definition() -> dict[str, Any]:
    return {
        "code": "FR-SANS-PARIS",
        "name": "France sans Paris",
        "description": "Zone de test",
        "from_date": "2026-10-15",
        "source_id": ["1", "2"],
        "operation": ["UNION", "DIFFERENCE"]
    }


@pytest.mark.parametrize(
        "role, forbidden", [
            ("VIEWER", ["zones:edit", "sources:manage", "users:manage"]),
            ("EDITOR", ["sources:manage", "users:manage"]),
        ]
)
@pytest.mark.parametrize("fragment", [False, True])
def test_privileged_markup_is_absent(
    front: Any,
    role: str,
    forbidden: list[str],
    fragment: bool
) -> None:
    """Les pages et les fragments omettent les actions non autorisees."""
    _, _, client = front
    headers = {"X-Test-Role": role, "HX-Request": str(fragment).lower()}
    response = client.get("/catalogs", headers=headers)
    assert response.status_code == 200
    for capability in forbidden:
        assert f'data-capability="{capability}"' not in response.text
    assert ("<!doctype html>" in response.text) != fragment


@pytest.mark.parametrize("path", ["/builder", "/builder/search", "/sources", "/administration"])
def test_viewer_cannot_call_privileged_routes(front: Any, path: str) -> None:
    """Une URL directe ne contourne pas les controles Jinja."""
    response = front[2].get(path, headers={"X-Test-Role": "VIEWER", "HX-Request": "true"})
    assert response.status_code == 403
    assert 'data-capability="sources:manage"' not in response.text


def test_preferences_are_persisted_and_scoped(front: Any) -> None:
    """La variante et le theme sont conserves pour la seule identite courante."""
    _, database, client = front
    assert _post(
        client,
        "/preferences",
        {
            "navigation": "workspace",
            "theme": "dark",
        },
        "VIEWER"
    ).status_code == 204
    assert 'data-navigation="workspace"' in client.get(
        "/profile",
        headers={"X-Test-Role": "VIEWER"},
    ).text
    assert 'data-theme="dark"' in client.get(
        "/profile",
        headers={"X-Test-Role": "VIEWER"},
    ).text
    assert 'data-navigation="workspace"' not in client.get(
        "/profile",
        headers={"X-Test-Role": "EDITOR"},
    ).text
    assert database.session.scalar(select(count()).select_from(UserPreferences)) == 1
    assert _post(client, "/preferences", {"navigation": "unknown"}, "VIEWER").status_code == 422


def test_preview_does_not_save_and_versions_are_immutable(front: Any) -> None:
    """L'apercu n'ecrit rien et chaque enregistrement cree une version distincte."""
    _, database, client = front
    response = _post(client, "/builder/preview", _definition(), "EDITOR")
    assert response.status_code == 200
    assert database.session.scalar(select(count()).select_from(GeoForged)) == 0
    assert _post(client, "/builder/save", _definition(), "EDITOR").status_code == 204
    assert _post(client, "/builder/save", _definition(), "EDITOR").status_code == 204
    assert list(
        database.session.scalars(select(GeoForged.version).order_by(GeoForged.version))
    ) == [1, 2]
    response = client.get("/catalogs/1", headers={"X-Test-Role": "VIEWER", "HX-Request": "true"})
    assert response.status_code == 200
    assert 'data-capability="zones:edit"' not in response.text
    assert len(client.get("/maps/options").json) == 2


@pytest.mark.parametrize(
    "format_name, signature", [
        ("yaml", b"code:"),
        ("geojson", b'{'),
        ("gpkg", b"SQLite format 3"),
        ("shp", b"PK"),
        ("postgis", b"BEGIN;"),
    ]
)
def test_viewer_exports_versions(front: Any, format_name: str, signature: bytes) -> None:
    """Tous les formats d'export sont accessibles au role VIEWER."""
    client = front[2]
    _post(client, "/builder/save", _definition(), "EDITOR")
    response = client.get(f"/catalogs/1/export/{format_name}", headers={"X-Test-Role": "VIEWER"})
    assert response.status_code == 200
    assert response.data.startswith(signature)


def test_sources_require_confirmation_and_preserve_dependencies(front: Any) -> None:
    """Le marquage ne supprime rien et une source utilisee reste protegee."""
    _, database, client = front
    response = _post(client, "/sources/delete-preview", {"source_id": "3"})
    assert response.status_code == 200
    assert database.session.get(GeographicZone, 3) is not None
    assert _post(client, "/sources/delete", {"source_id": "3"}).status_code == 422
    _post(client, "/builder/save", _definition(), "EDITOR")
    assert _post(
        client, "/sources/delete", {"source_id": "1", "confirmed": "yes"}
    ).status_code == 422
    assert database.session.scalar(select(count()).select_from(GeoForgedItem)) == 2
    assert _post(
        client, "/sources/delete", {"source_id": "3", "confirmed": "yes"}
    ).status_code == 204
    assert database.session.get(GeographicZone, 3) is None


def test_toml_preview_only_adds_after_validation(front: Any) -> None:
    """Un TOML ne supprime jamais l'existant et n'ajoute rien avant validation."""
    _, database, client = front
    entry = {
        "kind": "Test",
        "code": "NEW",
        "name": "Nouvelle source",
        "wkt": MultiPolygon([box(5, 5, 6, 6)]).wkt,
        "fingerprint": "new",
    }
    content = b'source_path = "https://naturalearth.s3.amazonaws.com"\n[[data_family.cultural]]\nname="Test"\nprecision=["low"]\nlink="admin_0_countries"\n'    # pylint: disable=C0301
    with patch("api.web.sources._read_entries", return_value=[entry]):
        response = _post(
            client,
            "/sources/preview",
            {"configuration": (BytesIO(content), "zones.toml")},
        )
    assert response.status_code == 200
    assert database.session.scalar(select(count()).select_from(GeographicZone)) == 3

    class TokenParser(HTMLParser):
        """Extrait le jeton d'apercu sans analyser le HTML par expressions regulieres."""
        token = ""

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = dict(attrs)
            if tag == "input" and values.get("name") == "token":
                self.token = values.get("value") or ""

    parser = TokenParser()
    parser.feed(response.text)
    assert parser.token
    assert _post(client, "/sources/apply", {"token": parser.token}).status_code == 204
    assert database.session.scalar(select(count()).select_from(GeographicZone)) == 4
    assert _post(client, "/sources/apply", {"token": parser.token}).status_code == 422


def test_yaml_roundtrip_and_invalid_input(front: Any) -> None:
    """Une definition exportee est reimportable et une saisie invalide est refusee."""
    client = front[2]
    _post(client, "/builder/save", _definition(), "EDITOR")
    content = client.get("/catalogs/1/export/yaml").data
    response = _post(
        client,
        "/catalogs/import",
        {"definition": (BytesIO(content), "zone.yaml")},
         "EDITOR",
    )
    assert response.status_code == 204
    assert _post(
        client,
        "/builder/preview",
        {**_definition(), "source_id": ["999", "2"]},
        "EDITOR",
    ).status_code == 422
    assert _post(
        client,
        "/catalogs/import",
        {"definition": (BytesIO(b"["), "zone.yaml")},
        "EDITOR",
    ).status_code == 422


def test_mutations_require_csrf(front: Any) -> None:
    """Une requete de mutation sans jeton CSRF est refusee."""
    assert front[2].post("/preferences", data={"theme": "dark"}).status_code == 400


@pytest.mark.parametrize(
    "content",[
        b'{}',
        b'source_path=12\ndata_family="incorrect"',
        b'source_path="https://naturalearth.s3.amazonaws.com"\n[data_family]\ncultural="incorrect"',
    ],
)
def test_invalid_toml_is_rejected_without_changes(front: Any, content: bytes) -> None:
    """Une structure TOML invalide n'ecrit rien en base."""
    _, database, client = front
    response = _post(
        client,
        "/sources/preview",
        {"configuration": (BytesIO(content), "zones.toml")},
    )
    assert response.status_code == 422
    assert database.session.scalar(select(count()).select_from(GeographicZone)) == 3


def test_preferences_follow_authentication_context(front: Any) -> None:
    """Les preferences d'un compte purge ne sont pas reutilisees par un autre."""
    _, database, client = front
    _post(client, "/preferences", {"navigation": "tabs", "theme": "light"}, "VIEWER")
    service = UserService(database.session)
    service.synchronize_auth_context("internal")
    service.synchronize_auth_context("external", "https://test.example")
    assert database.session.scalar(select(count()).select_from(UserPreferences)) == 0
