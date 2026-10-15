"""Tests des parcours d'authentification GeoReforge."""

from __future__ import annotations

from typing import Any, Iterator, cast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
import logging
from pathlib import Path
from types import SimpleNamespace

from authlib.integrations.base_client.errors import OAuthError
from flask import Flask, jsonify, redirect
from flask.testing import FlaskClient
from joserfc.errors import BadSignatureError
import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout
from sqlalchemy import Engine, select, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from api.main import create_app
from api.common.db_objects import Base, table_key
from api.common.db_objects.users import AuthRuntimeState, Group as DbGroup
from api.common.db_objects.users import User as DbUser
from api.common.db_objects.users import UserGroup, UserIdentity, UserLoginState, UserSession
from api.config import DatabaseConfig, FlaskSettings
from auth.decorators import require_group
from auth.manager import AuthManager
from auth.models import User
from auth.services import SessionService, UserService
import auth.services.user_service as user_service_module


AUTH_TABLE_NAMES = (
    "users",
    "groups",
    "user_groups",
    "user_sessions",
    "user_login_states",
    "user_identities",
    "auth_runtime_state",
    "user_preferences",
)
TEST_SECRET = "test-only-secret-key-that-is-not-used-in-production"
TEST_PASSWORD = "test-only-password"


@dataclass
class AuthDatabase:
    """Base SQLite isolee pour un test d'authentification."""

    engine: Engine
    session: scoped_session[Session]
    users: UserService


@pytest.fixture(autouse=True)
def disable_failure_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evite d'attendre cinq secondes dans les tests fonctionnels."""
    monkeypatch.setattr(user_service_module, "sleep", lambda _seconds: None)    # type: ignore


@pytest.fixture(name="auth_database")
def auth_database_fixture(tmp_path: Path) -> Iterator[AuthDatabase]:
    """Fournit une base SQLite temporaire avec les tables d'authentification."""
    database_path = tmp_path / "auth.sqlite"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    tables = [Base.metadata.tables[table_key(name)] for name in AUTH_TABLE_NAMES]
    Base.metadata.create_all(engine, tables=tables)
    session = scoped_session(
        sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    )
    database = AuthDatabase(engine=engine, session=session, users=UserService(session))
    database.users.ensure_groups()
    try:
        yield database
    finally:
        session.remove()
        engine.dispose()


def make_app(
    database: AuthDatabase,
    mode: str = "internal",
    *,
    secure_connection: bool = False,
) -> Flask:
    """Construit l'application avec la base SQLite isolee du test."""
    settings_values: dict[str, Any] = {
        "AUTH_MODE": mode,
        "FLASK_ENV": "development" if mode == "none" else "production",
        "SECRET_KEY": TEST_SECRET,
        "ADMIN_USERNAME": "test-admin",
        "ADMIN_PASSWORD": TEST_PASSWORD,
        "ENFORCE_SECURE_CONNECTION": secure_connection,
    }
    if mode == "external":
        settings_values.update(
            {
                "OIDC_ISSUER": "https://issuer.example.test",
                "OIDC_CLIENT_ID": "test-client",
                "OIDC_CLIENT_SECRET": "test-client-secret",
                "OIDC_REDIRECT_URI": "https://app.example.test/auth/callback",
            }
        )
    settings = FlaskSettings(**settings_values)
    database_config = cast(DatabaseConfig, SimpleNamespace(session=database.session))
    app = create_app(settings, database_config)
    app.testing = True
    return app


@pytest.mark.parametrize("mode", ["internal", "external"])
@pytest.mark.parametrize("secret", ["default_secret_key", "x" * 31])
def test_authenticated_modes_reject_default_or_short_secret(
    mode: str,
    secret: str,
) -> None:
    """Les modes authentifiés refusent le secret par défaut et les clés courtes."""
    settings_values: dict[str, str] = {
        "AUTH_MODE": mode,
        "SECRET_KEY": secret,
        "ADMIN_PASSWORD": TEST_PASSWORD,
    }
    if mode == "external":
        settings_values.update(
            {
                "OIDC_ISSUER": "https://issuer.example.test",
                "OIDC_CLIENT_ID": "test-client",
                "OIDC_CLIENT_SECRET": "test-client-secret",
                "OIDC_REDIRECT_URI": "https://app.example.test/auth/callback",
            }
        )

    with pytest.raises(ValueError, match="32 caractères"):
        FlaskSettings(**settings_values)    # type: ignore


@pytest.mark.parametrize("mode", ["internal", "external"])
def test_authenticated_modes_accept_long_secret(mode: str) -> None:
    """Une clé personnalisée d'au moins 32 caractères est acceptée."""
    settings_values: dict[str, str] = {
        "AUTH_MODE": mode,
        "SECRET_KEY": TEST_SECRET,
        "ADMIN_PASSWORD": TEST_PASSWORD,
    }
    if mode == "external":
        settings_values.update(
            {
                "OIDC_ISSUER": "https://issuer.example.test",
                "OIDC_CLIENT_ID": "test-client",
                "OIDC_CLIENT_SECRET": "test-client-secret",
                "OIDC_REDIRECT_URI": "https://app.example.test/auth/callback",
            }
        )

    assert FlaskSettings(**settings_values).SECRET_KEY == TEST_SECRET    # type: ignore


@pytest.mark.parametrize("secret", ["default_secret_key", "short"])
def test_none_mode_keeps_local_secret_defaults(secret: str) -> None:
    """Le mode none reste démarrable sans secret de production."""
    assert FlaskSettings(
        AUTH_MODE="none",
        FLASK_ENV="development",
        SECRET_KEY=secret,
    ).SECRET_KEY == secret


def test_production_none_mode_requires_explicit_anonymous_access_opt_in() -> None:
    """Le mode none en production requiert une activation explicite."""
    with pytest.raises(ValueError, match="ALLOW_ANONYMOUS_ACCESS"):
        FlaskSettings(AUTH_MODE="none", FLASK_ENV="production")

    settings = FlaskSettings(
        AUTH_MODE="none",
        FLASK_ENV="production",
        ALLOW_ANONYMOUS_ACCESS=True,
    )
    assert settings.ALLOW_ANONYMOUS_ACCESS


@pytest.mark.parametrize(
    "cookie_name",
    ["session", "", "bad name", "bad;name"],
)
def test_cookie_names_must_be_valid_and_distinct(cookie_name: str) -> None:
    """Les noms invalides et la collision avec le cookie Flask sont refusés."""
    with pytest.raises(ValueError):
        FlaskSettings(AUTH_COOKIE_NAME=cookie_name)


def test_flask_cookie_settings_follow_secure_connection() -> None:
    """Le cookie Flask reprend le réglage HTTPS et conserve ses autres attributs."""
    settings = FlaskSettings(ENFORCE_SECURE_CONNECTION=True)

    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.SESSION_COOKIE_PATH == "/"


def test_flask_cookie_settings_reject_inconsistent_values() -> None:
    """Les options explicites incompatibles avec le contrat cookie sont refusées."""
    with pytest.raises(ValueError, match="SESSION_COOKIE_SECURE"):
        FlaskSettings(
            ENFORCE_SECURE_CONNECTION=True,
            SESSION_COOKIE_SECURE=False,
        )
    for setting_name, setting_value in (
        ("SESSION_COOKIE_HTTPONLY", False),
        ("SESSION_COOKIE_SAMESITE", "None"),
        ("SESSION_COOKIE_PATH", "/auth"),
    ):
        with pytest.raises(ValueError):
            FlaskSettings(**{setting_name: setting_value})  # type: ignore


def test_flask_session_cookie_has_secure_attributes_by_setting(
    auth_database: AuthDatabase,
) -> None:
    """Le cookie Flask applique les attributs communs et suit le réglage Secure."""
    for secure_connection in (False, True):
        client = make_app(
            auth_database,
            secure_connection=secure_connection,
        ).test_client()
        response = client.get(
            "/auth/csrf",
            base_url="https://localhost" if secure_connection else "http://localhost",
        )
        assert response.status_code == 200
        session_cookie = next(
            value
            for value in response.headers.getlist("Set-Cookie")
            if value.startswith("session=")
        )
        assert "HttpOnly" in session_cookie
        assert "SameSite=Lax" in session_cookie
        assert "Path=/" in session_cookie
        assert ("Secure" in session_cookie) is secure_connection


def test_secure_connection_rejects_http_except_health(
    auth_database: AuthDatabase,
) -> None:
    """Le réglage impose HTTPS sans redirection et laisse la sonde HTTP accessible."""
    client = make_app(auth_database, secure_connection=True).test_client()

    response = client.get("/auth/csrf")

    assert response.status_code == 403
    assert "Location" not in response.headers
    assert client.get("/health").status_code == 200
    assert client.get("/auth/csrf", base_url="https://localhost").status_code == 200


def test_local_http_remains_available_when_secure_connection_is_disabled(
    auth_database: AuthDatabase,
) -> None:
    """Le profil local HTTP reste utilisable quand la contrainte est désactivée."""
    client = make_app(auth_database).test_client()

    assert client.get("/auth/csrf").status_code == 200


def make_internal_user(
    database: AuthDatabase,
    username: str = "test-user",
    *,
    password: str = TEST_PASSWORD,
    groups: list[str] | None = None,
) -> User:
    """Cree un compte interne avec les groupes demandes."""
    return database.users.create_user(
        username,
        f"{username}@example.test",
        password,
        group_names=groups or [],
    )


def csrf_headers(
    client: FlaskClient,
    base_url: str = "http://localhost",
) -> dict[str, str]:
    """Recupere un jeton CSRF de test pour une requete POST."""
    response = client.get("/auth/csrf", base_url=base_url)
    assert response.status_code == 200, response.get_data(as_text=True)
    token = response.get_json()["csrf_token"]
    return {"X-CSRFToken": token}


def test_none_mode_exposes_virtual_identity_and_disables_login(
    auth_database: AuthDatabase,    # pylint: disable=W0613
) -> None:
    """Le mode none retourne l'identite locale et refuse le login HTTP."""
    client = make_app(auth_database, "none").test_client()

    identity_response = client.get("/auth/me")
    assert identity_response.status_code == 200
    assert identity_response.get_json()["user"] == {
        "id": "local",
        "username": "local",
        "groups": ["ADMIN"],
        "auth_source": "none",
    }

    response = client.post(
        "/auth/login",
        json={},
        headers=csrf_headers(client),
    )
    assert response.status_code == 405
    assert not auth_database.session.scalars(select(UserSession.id)).first()


@pytest.mark.parametrize("secure_connection", [False, True])
def test_internal_login_success_sets_auth_cookie_and_identity(
    auth_database: AuthDatabase,    # pylint: disable=W0601
    secure_connection: bool,
) -> None:
    """Un login interne valide cree une session et son cookie protege."""
    make_internal_user(auth_database, groups=["VIEWER"])
    client = make_app(auth_database, secure_connection=secure_connection).test_client()
    base_url = "https://localhost" if secure_connection else "http://localhost"
    request_headers = csrf_headers(client, base_url=base_url)
    if secure_connection:
        request_headers["Referer"] = f"{base_url}/auth/login"

    response = client.post(
        "/auth/login",
        json={"username": "test-user", "password": TEST_PASSWORD},
        headers=request_headers,
        base_url=base_url,
    )

    assert response.status_code == 200
    assert response.get_json()["user"]["username"] == "test-user"
    auth_cookie = next(
        value
        for value in response.headers.getlist("Set-Cookie")
        if value.startswith("georeforge_session=")
    )
    assert "HttpOnly" in auth_cookie
    assert ("Secure" in auth_cookie) is secure_connection
    assert "SameSite=Lax" in auth_cookie
    assert "Path=/" in auth_cookie

    current = client.get("/auth/me", base_url=base_url)
    assert current.status_code == 200
    assert current.get_json()["user"]["groups"] == ["VIEWER"]


def test_internal_login_requires_csrf(auth_database: AuthDatabase) -> None:
    """Les POST d'authentification sans jeton CSRF sont refuses."""
    client = make_app(auth_database).test_client()

    response = client.post(
        "/auth/login",
        json={"username": "missing", "password": "wrong"},
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("payload", "username"),
    [
        ({"password": "wrong"}, None),
        ({"username": "test-user"}, "test-user"),
        ({"username": "unknown-user", "password": "wrong"}, "unknown-user"),
        ({"username": "test-user", "password": "wrong"}, "test-user"),
    ],
    ids=["username-absent", "password-absent", "user-inconnu", "mauvais-mot-de-passe"],
)
def test_internal_invalid_credentials_are_rejected(
    auth_database: AuthDatabase,
    payload: dict[str, str],
    username: str | None,
) -> None:
    """Les identifiants incomplets ou incorrects retournent une erreur generique."""
    make_internal_user(auth_database)
    client = make_app(auth_database).test_client()

    response = client.post("/auth/login", json=payload, headers=csrf_headers(client))

    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid username or password"}
    if username is not None and username != "unknown-user":
        state = auth_database.session.scalar(select(UserLoginState.failed_attempts))
        assert state == 1


def test_failed_attempts_use_the_same_delay(
    auth_database: AuthDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compte inconnu, mot de passe absent et mauvais mot de passe sont temporises."""
    make_internal_user(auth_database)
    delays: list[float] = []
    monkeypatch.setattr(user_service_module, "sleep", delays.append)
    backend = make_app(auth_database).extensions["auth_manager"].backend

    assert backend.authenticate({"username": "test-user", "password": "wrong"}) is None
    assert backend.authenticate({"username": "unknown-user", "password": "wrong"}) is None
    assert backend.authenticate({"username": "test-user"}) is None
    assert backend.authenticate({"password": "wrong"}) is None

    assert delays == [5, 5, 5, 5]
    assert len(auth_database.session.scalars(select(UserLoginState.user_id)).all()) == 1


def test_lock_after_six_failures_success_resets_and_service_unlocks(
    auth_database: AuthDatabase,
) -> None:
    """Cinq echecs restent recuperables, le sixieme verrouille jusqu'au reset."""
    user = make_internal_user(auth_database)

    for _ in range(5):
        assert auth_database.users.authenticate(user.username, "wrong") is None
    attempts, locked = auth_database.session.execute(
        select(UserLoginState.failed_attempts, UserLoginState.locked)
    ).one()
    assert (attempts, locked) == (5, False)

    assert auth_database.users.authenticate(user.username, TEST_PASSWORD) is not None
    attempts, locked = auth_database.session.execute(
        select(UserLoginState.failed_attempts, UserLoginState.locked)
    ).one()
    assert (attempts, locked) == (0, False)

    for _ in range(6):
        assert auth_database.users.authenticate(user.username, "wrong") is None
    attempts, locked = auth_database.session.execute(
        select(UserLoginState.failed_attempts, UserLoginState.locked)
    ).one()
    assert (attempts, locked) == (6, True)
    assert auth_database.users.authenticate(user.username, TEST_PASSWORD) is None
    assert auth_database.users.reset_login_lock(int(user.id))
    assert auth_database.users.authenticate(user.username, TEST_PASSWORD) is not None
    assert not auth_database.users.reset_login_lock(-1)


def test_unknown_user_does_not_create_persistent_failure_state(
    auth_database: AuthDatabase,
) -> None:
    """Les essais sur un nom inconnu n'ajoutent pas de lignes persistantes."""
    for index in range(20):
        assert auth_database.users.authenticate(f"unknown-{index}", "wrong") is None

    assert not auth_database.session.scalars(select(UserLoginState.user_id)).first()


def test_forced_login_requests_lock_the_known_account(
    auth_database: AuthDatabase,
) -> None:
    """Des POST repetes ne peuvent plus authentifier le compte apres le seuil."""
    make_internal_user(auth_database)
    client = make_app(auth_database).test_client()
    headers = csrf_headers(client)

    for _ in range(6):
        response = client.post(
            "/auth/login",
            json={"username": "test-user", "password": "wrong"},
            headers=headers,
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/login",
        json={"username": "test-user", "password": TEST_PASSWORD},
        headers=headers,
    )
    assert response.status_code == 401


def test_simultaneous_failed_attempts_are_counted_atomically(
    auth_database: AuthDatabase,
) -> None:
    """Les echecs concurrents ne perdent pas d'increments de compteur."""
    user = make_internal_user(auth_database)

    def submit_attempt(_index: int) -> None:
        try:
            assert auth_database.users.authenticate(user.username, "wrong") is None
        finally:
            auth_database.session.remove()

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(submit_attempt, range(8)))

    attempts, locked = auth_database.session.execute(
        select(UserLoginState.failed_attempts, UserLoginState.locked)
    ).one()
    assert (attempts, locked) == (6, True)


def test_group_access_respects_active_association(
    auth_database: AuthDatabase,
) -> None:
    """Le decorateur autorise un groupe actif puis le refuse apres desactivation."""
    user = make_internal_user(auth_database, groups=["VIEWER"])
    app = make_app(auth_database)
    app.add_url_rule(
        "/viewer",
        "viewer",
        require_group("VIEWER")(lambda: jsonify(success=True)),
    )
    client = app.test_client()
    response = client.post(
        "/auth/login",
        json={"username": user.username, "password": TEST_PASSWORD},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    assert client.get("/viewer").status_code == 200

    association = auth_database.session.scalar(
        select(UserGroup).where(UserGroup.user_id == int(user.id))
    )
    assert association is not None
    association.activated = False
    auth_database.session.commit()

    assert client.get("/viewer").status_code == 403


@pytest.mark.parametrize(
    ("user_groups", "required_group", "expected_status"),
    [
        (["ADMIN"], "ADMIN", 200),
        (["ADMIN"], "EDITOR", 200),
        (["ADMIN"], "VIEWER", 200),
        (["EDITOR"], "ADMIN", 403),
        (["EDITOR"], "VIEWER", 200),
        (["VIEWER"], "EDITOR", 403),
    ],
)
def test_group_access_follows_role_hierarchy(
    auth_database: AuthDatabase,
    monkeypatch: pytest.MonkeyPatch,
    user_groups: list[str],
    required_group: str,
    expected_status: int,
) -> None:
    """Les groupes ADMIN, EDITOR et VIEWER suivent leur ordre hierarchique."""
    from auth import decorators # pylint: disable=C0415

    monkeypatch.setattr(
        decorators,
        "get_current_user",
        lambda: User(
            id="test-user",
            username="test-user",
            groups=user_groups,
            auth_source="internal",
        ),
    )
    app = make_app(auth_database)
    app.add_url_rule(
        "/protected",
        "protected",
        require_group(required_group)(lambda: jsonify(success=True)),
    )

    assert app.test_client().get("/protected").status_code == expected_status


def test_none_mode_virtual_admin_inherits_all_roles(auth_database: AuthDatabase) -> None:
    """Le mode none accorde les niveaux inferieurs via son identite ADMIN."""
    app = make_app(auth_database, mode="none")
    for group in ("ADMIN", "EDITOR", "VIEWER"):
        app.add_url_rule(
            f"/protected/{group.lower()}",
            f"protected_{group.lower()}",
            require_group(group)(lambda: jsonify(success=True)),
        )

    client = app.test_client()

    assert [
        client.get(f"/protected/{group.lower()}").status_code
        for group in ("ADMIN", "EDITOR", "VIEWER")
    ] == [200, 200, 200]
    assert client.get("/health").status_code == 200


def test_user_crud_and_collisions_leave_session_usable(
    auth_database: AuthDatabase,
) -> None:
    """Le CRUD fonctionne et un doublon ne laisse pas la session en echec."""
    user = make_internal_user(auth_database, groups=["VIEWER"])
    updated = auth_database.users.update_user(
        int(user.id),
        username="renamed-user",
        email="renamed@example.test",
        group_names=["EDITOR"],
    )
    assert updated is not None
    assert updated.username == "renamed-user"
    assert updated.groups == ["EDITOR"]
    assert [entry.username for entry in auth_database.users.list_users()] == ["renamed-user"]

    with pytest.raises(SQLAlchemyError):
        auth_database.users.create_user(
            "renamed-user",
            "another@example.test",
            "another-password",
        )

    assert auth_database.users.get(int(user.id)) is not None
    assert auth_database.users.delete_user(int(user.id))
    assert auth_database.users.get(int(user.id)) is None
    assert auth_database.session.get(UserLoginState, int(user.id)) is None


@pytest.mark.parametrize(
    ("username", "email"),
    [
        ("existing-user", "new@example.test"),
        ("new-user", "existing@example.test"),
    ],
    ids=["username-duplique", "email-duplique"],
)
def test_username_and_email_collisions_roll_back(
    auth_database: AuthDatabase,
    username: str,
    email: str,
) -> None:
    """Les contraintes uniques sont appliquees et la session reste reutilisable."""
    auth_database.users.create_user(
        "existing-user",
        "existing@example.test",
        TEST_PASSWORD,
    )

    with pytest.raises(SQLAlchemyError):
        auth_database.users.create_user(username, email, "another-password")

    assert len(auth_database.users.list_users()) == 1


def test_failed_user_update_rolls_back_all_field_changes(
    auth_database: AuthDatabase,
) -> None:
    """Une erreur tardive d'update annule aussi les champs deja modifies."""
    user = make_internal_user(auth_database)

    with pytest.raises(ValueError, match="Groupes inconnus"):
        auth_database.users.update_user(
            int(user.id),
            username="partially-renamed",
            group_names=["MISSING"],
        )

    current = auth_database.users.get(int(user.id))
    assert current is not None
    assert current.username == user.username
    assert auth_database.users.create_user(
        "after-rollback",
        "after-rollback@example.test",
        TEST_PASSWORD,
    )


def test_concurrent_external_provisioning_is_idempotent(
    auth_database: AuthDatabase,
) -> None:
    """Des callbacks concurrents pour un meme sujet convergent vers un seul compte."""
    def synchronize(_index: int) -> User:
        try:
            return auth_database.users.sync_external_user(
                "https://issuer.example.test",
                {"sub": "concurrent-subject", "groups": ["VIEWER"]},
            )
        finally:
            auth_database.session.remove()

    with ThreadPoolExecutor(max_workers=4) as executor:
        users = list(executor.map(synchronize, range(4)))

    assert len({user.id for user in users}) == 1
    assert users[0].auth_source == "external"
    assert len(auth_database.session.scalars(select(DbUser.id)).all()) == 1


def test_admin_bootstrap_is_idempotent(auth_database: AuthDatabase) -> None:
    """Deux bootstraps conservent un seul administrateur, ses groupes et son etat."""
    settings = FlaskSettings(
        AUTH_MODE="internal",
        SECRET_KEY=TEST_SECRET,
        ADMIN_USERNAME="initial-admin",
        ADMIN_PASSWORD=TEST_PASSWORD,
    )

    AuthManager.initialize_database(auth_database.session, settings)
    AuthManager.initialize_database(auth_database.session, settings)

    assert len(auth_database.session.scalars(select(UserLoginState.user_id)).all()) == 1
    assert auth_database.session.scalar(
        select(DbGroup.id).where(DbGroup.name == "ADMIN")
    ) is not None
    assert len(auth_database.users.list_users()) == 1


def test_admin_bootstrap_does_not_restore_removed_admin_group(
    auth_database: AuthDatabase,
) -> None:
    """Un redemarrage respecte le retrait explicite du groupe ADMIN."""
    settings = FlaskSettings(
        AUTH_MODE="internal",
        SECRET_KEY=TEST_SECRET,
        ADMIN_USERNAME="initial-admin",
        ADMIN_PASSWORD=TEST_PASSWORD,
    )
    AuthManager.initialize_database(auth_database.session, settings)
    admin = auth_database.users.list_users()[0]
    auth_database.users.update_user(int(admin.id), group_names=[])
    restarted_settings = FlaskSettings(
        AUTH_MODE="internal",
        SECRET_KEY=TEST_SECRET,
        ADMIN_USERNAME="initial-admin",
    )

    AuthManager.initialize_database(auth_database.session, restarted_settings)

    assert auth_database.users.get(int(admin.id)).groups == []  # type: ignore[union-attr]


def test_admin_bootstrap_requires_password_only_when_creating_account(
    auth_database: AuthDatabase,
) -> None:
    """Sans mot de passe, le bootstrap refuse seulement la creation initiale."""
    settings = FlaskSettings(
        AUTH_MODE="internal",
        SECRET_KEY=TEST_SECRET,
        ADMIN_USERNAME="missing-admin",
    )

    with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
        AuthManager.initialize_database(auth_database.session, settings)

    assert auth_database.users.list_users() == []


def test_concurrent_admin_bootstrap_is_idempotent(auth_database: AuthDatabase) -> None:
    """Deux demarrages concurrents ne creent qu'un compte administrateur."""
    settings = FlaskSettings(
        AUTH_MODE="internal",
        SECRET_KEY=TEST_SECRET,
        ADMIN_USERNAME="concurrent-admin",
        ADMIN_PASSWORD=TEST_PASSWORD,
    )

    def initialize(_index: int) -> None:
        AuthManager.initialize_database(auth_database.session, settings)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(initialize, range(2)))

    assert [user.username for user in auth_database.users.list_users()] == [
        "concurrent-admin"
    ]


def test_password_change_and_disable_revoke_all_sessions(
    auth_database: AuthDatabase,
) -> None:
    """Le mot de passe change et la desactivation invalident toutes les sessions."""
    user = make_internal_user(auth_database)
    sessions = SessionService(auth_database.session)
    first = sessions.create(int(user.id))
    second = sessions.create(int(user.id))

    auth_database.users.update_user(int(user.id), password="changed-password")
    assert sessions.get_user_id(first) is None
    assert sessions.get_user_id(second) is None

    third = sessions.create(int(user.id))
    fourth = sessions.create(int(user.id))
    auth_database.users.update_user(int(user.id), enabled=False)
    assert sessions.get_user_id(third) is None
    assert sessions.get_user_id(fourth) is None


def test_expired_session_is_rejected_and_deleted(auth_database: AuthDatabase) -> None:
    """Une session expiree ne fournit plus d'identite et est supprimee."""
    user = make_internal_user(auth_database)
    sessions = SessionService(auth_database.session, lifetime=timedelta(seconds=-1))
    token = sessions.create(int(user.id))

    assert sessions.get_user_id(token) is None
    assert not auth_database.session.scalars(select(UserSession.id)).first()


def test_password_is_absent_from_success_and_failure_logs(
    auth_database: AuthDatabase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Le mot de passe n'apparait jamais dans les logs de login."""
    make_internal_user(auth_database)
    app = make_app(auth_database)
    manager = cast(AuthManager, app.extensions["auth_manager"])
    marker = "password-log-marker-never-print"

    with caplog.at_level(logging.WARNING, logger="auth.manager"):
        assert manager.authenticate({"username": "test-user", "password": marker}) is None
        assert marker not in caplog.text
        caplog.clear()
        assert manager.authenticate({"username": "test-user", "password": TEST_PASSWORD})
        assert marker not in caplog.text
        assert TEST_PASSWORD not in caplog.text


def test_external_mode_callback_creates_session_and_maps_allowed_groups(
    auth_database: AuthDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le callback simule cree une session et ne conserve que les groupes autorises."""
    app = make_app(auth_database, "external", secure_connection=True)
    manager = cast(AuthManager, app.extensions["auth_manager"])
    external_user = auth_database.users.sync_external_user(
        "https://issuer.example.test",
        {"sub": "test-subject", "groups": ["ADMIN", "UNTRUSTED"]},
    )
    token = SessionService(auth_database.session).create(int(external_user.id))
    monkeypatch.setattr(manager, "complete_login", lambda: (external_user, token))
    client = app.test_client()

    response = client.get("/auth/callback", base_url="https://localhost")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.get_json()["user"]["groups"] == ["ADMIN"]
    auth_cookie = next(
        value
        for value in response.headers.getlist("Set-Cookie")
        if value.startswith("georeforge_session=")
    )
    assert "HttpOnly" in auth_cookie
    assert "Secure" in auth_cookie
    assert client.get("/auth/me", base_url="https://localhost").status_code == 200


def test_external_callback_rejects_disabled_user_without_creating_session(
    auth_database: AuthDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un compte OIDC desactive est refuse avant le callback et sans session."""
    app = make_app(auth_database, "external")
    manager = cast(AuthManager, app.extensions["auth_manager"])
    user = auth_database.users.sync_external_user(
        "https://issuer.example.test",
        {"sub": "disabled-subject", "groups": ["ADMIN"]},
    )
    auth_database.users.update_user(int(user.id), enabled=False)
    sessions_before = auth_database.session.scalars(
        select(UserSession.id).where(UserSession.user_id == int(user.id))
    ).all()
    monkeypatch.setattr(
        manager,
        "complete_login",
        lambda: auth_database.users.sync_external_user(
            "https://issuer.example.test",
            {"sub": "disabled-subject", "groups": ["VIEWER"]},
        ),
    )

    response = app.test_client().get("/auth/callback")

    assert response.status_code == 401
    assert "Set-Cookie" not in response.headers
    assert auth_database.session.scalars(
        select(UserSession.id).where(UserSession.user_id == int(user.id))
    ).all() == sessions_before
    assert auth_database.session.scalar(
        select(UserGroup.activated).where(UserGroup.user_id == int(user.id))
    ) is True


def test_user_provenance_is_persisted_and_external_identity_cannot_be_renamed(
    auth_database: AuthDatabase,
) -> None:
    """La source survit aux lectures et mises a jour sans conversion implicite."""
    external = auth_database.users.sync_external_user(
        "https://issuer.example.test",
        {"sub": "provenance-subject", "groups": ["VIEWER"]},
    )
    internal = make_internal_user(auth_database, username="oidc_looks_internal")

    assert auth_database.users.get(int(external.id)).auth_source == "external"  # type: ignore
    assert next(
        user for user in auth_database.users.list_users() if user.id == external.id
    ).auth_source == "external"
    updated = auth_database.users.update_user(
        int(external.id),
        group_names=["EDITOR"],
    )
    assert updated is not None
    assert updated.auth_source == "external"
    assert auth_database.users.get(int(internal.id)).auth_source == "internal"  # type: ignore
    with pytest.raises(ValueError, match="identité externe"):
        auth_database.users.update_user(int(external.id), username="converted")


def test_changing_auth_mode_purges_all_persisted_authentication_state(
    auth_database: AuthDatabase,
) -> None:
    """Le passage de internal a external purge comptes et sessions en base."""
    internal_settings = FlaskSettings(
        AUTH_MODE="internal",
        SECRET_KEY=TEST_SECRET,
        ADMIN_USERNAME="initial-admin",
        ADMIN_PASSWORD=TEST_PASSWORD,
    )
    AuthManager.initialize_database(auth_database.session, internal_settings)
    user = make_internal_user(auth_database)
    sessions = SessionService(auth_database.session)
    token = sessions.create(int(user.id))
    external_settings = FlaskSettings(
        AUTH_MODE="external",
        SECRET_KEY=TEST_SECRET,
        OIDC_ISSUER="https://issuer.example.test",
        OIDC_CLIENT_ID="test-client",
        OIDC_CLIENT_SECRET="test-client-secret",
        OIDC_REDIRECT_URI="https://app.example.test/auth/callback",
    )

    AuthManager.initialize_database(auth_database.session, external_settings)

    assert auth_database.session.get(DbUser, int(user.id)) is None
    assert sessions.get_user_id(token) is None
    assert auth_database.session.scalars(select(UserGroup.id)).all() == []
    state = auth_database.session.get(AuthRuntimeState, 1)
    assert state is not None
    assert state.auth_mode == "external"

    external_user = auth_database.users.sync_external_user(
        "https://issuer.example.test",
        {"sub": "issuer-change-subject", "groups": ["VIEWER"]},
    )
    external_token = sessions.create(int(external_user.id))
    changed_issuer_settings = external_settings.model_copy(
        update={"OIDC_ISSUER": "https://issuer.example.test/"}
    )

    AuthManager.initialize_database(auth_database.session, changed_issuer_settings)

    assert auth_database.users.list_users() == []
    assert sessions.get_user_id(external_token) is None
    state = auth_database.session.get(AuthRuntimeState, 1)
    assert state is not None
    assert state.issuer == "https://issuer.example.test/"


def test_legacy_external_identity_is_completed_on_matching_callback(
    auth_database: AuthDatabase,
) -> None:
    """Les comptes OIDC precedents sont marques external sans issuer invente."""
    user = auth_database.users.sync_external_user(
        "https://issuer.example.test",
        {"sub": "legacy-subject", "groups": ["VIEWER"]},
    )
    auth_database.session.delete(auth_database.session.get(UserIdentity, int(user.id)))
    auth_database.session.commit()
    settings = FlaskSettings(
        AUTH_MODE="external",
        SECRET_KEY=TEST_SECRET,
        OIDC_ISSUER="https://issuer.example.test",
        OIDC_CLIENT_ID="test-client",
        OIDC_CLIENT_SECRET="test-client-secret",
        OIDC_REDIRECT_URI="https://app.example.test/auth/callback",
    )

    AuthManager.initialize_database(auth_database.session, settings)

    identity = auth_database.session.get(UserIdentity, int(user.id))
    assert identity is not None
    assert identity.auth_source == "external"
    assert identity.issuer is None
    assert identity.subject is None
    updated = auth_database.users.sync_external_user(
        "https://issuer.example.test",
        {"sub": "legacy-subject", "groups": ["VIEWER"]},
    )
    assert updated.auth_source == "external"
    assert identity.issuer == "https://issuer.example.test"
    assert identity.subject == "legacy-subject"


def test_external_login_route_starts_redirect(
    auth_database: AuthDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET login delegue la redirection au backend OIDC."""
    app = make_app(auth_database, "external")
    manager = cast(AuthManager, app.extensions["auth_manager"])
    monkeypatch.setattr(
        manager,
        "begin_login",
        lambda: redirect("https://issuer.example.test/authorize"),
    )

    response = app.test_client().get("/auth/login")

    assert response.status_code == 302
    assert response.headers["Location"] == "https://issuer.example.test/authorize"
    assert response.headers["Cache-Control"] == "no-store"
    assert manager.backend.client.client_kwargs["default_timeout"] == 10    # type: ignore


@pytest.mark.parametrize(
    "error",
    [OAuthError(description="invalid state"), ValueError("invalid profile"), KeyError("sub")],
    ids=["state-invalide", "profil-invalide", "claim-absent"],
)
def test_oidc_callback_rejects_expected_authentication_errors(
    auth_database: AuthDatabase,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    """Les erreurs OIDC traitees en V0 ne creent ni session ni cookie."""
    app = make_app(auth_database, "external")
    manager = cast(AuthManager, app.extensions["auth_manager"])

    def fail_login() -> tuple[User, str]:
        raise error

    monkeypatch.setattr(manager, "complete_login", fail_login)
    response = app.test_client().get("/auth/callback")

    assert response.status_code == 401
    assert not any(
        value.startswith("georeforge_session=")
        for value in response.headers.getlist("Set-Cookie")
    )
    assert not auth_database.session.scalars(select(UserSession.id)).first()


def test_oidc_bad_signature_is_not_accepted(
    auth_database: AuthDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une erreur de signature OIDC ne produit jamais une session authentifiee."""
    app = make_app(auth_database, "external")
    manager = cast(AuthManager, app.extensions["auth_manager"])

    def fail_signature() -> tuple[User, str]:
        raise BadSignatureError()

    monkeypatch.setattr(manager, "complete_login", fail_signature)
    client = app.test_client()

    response = client.get("/auth/callback")

    assert response.status_code == 401
    assert response.get_json() == {"error": "OIDC authentication failed"}
    assert not auth_database.session.scalars(select(UserSession.id)).first()


@pytest.mark.parametrize(
    "network_error",
    [
        RequestsConnectionError("sensitive-provider-response"),
        RequestsTimeout("sensitive-provider-response"),
    ],
    ids=["connection-error", "timeout"],
)
def test_oidc_network_errors_are_unavailable_and_do_not_leak_details(
    auth_database: AuthDatabase,
    monkeypatch: pytest.MonkeyPatch,
    network_error: Exception,
) -> None:
    """Une panne IdP donne une erreur 503 generique au login et au callback."""
    app = make_app(auth_database, "external")
    manager = cast(AuthManager, app.extensions["auth_manager"])

    def fail_network() -> None:
        raise network_error

    monkeypatch.setattr(manager, "begin_login", fail_network)
    login_response = app.test_client().get("/auth/login")
    assert login_response.status_code == 503
    assert "sensitive-provider-response" not in login_response.get_data(as_text=True)

    monkeypatch.setattr(manager, "complete_login", fail_network)
    callback_response = app.test_client().get("/auth/callback")
    assert callback_response.status_code == 503
    assert "sensitive-provider-response" not in callback_response.get_data(as_text=True)
    assert not auth_database.session.scalars(select(UserSession.id)).first()


def test_auth_errors_are_json_and_auth_responses_are_not_cached(
    auth_database: AuthDatabase,
) -> None:
    """Les erreurs CSRF/401 et les réponses sensibles ont un contrat HTTP explicite."""
    client = make_app(auth_database).test_client()

    csrf_response = client.get("/auth/csrf")
    identity_response = client.get("/auth/me")
    csrf_error = client.post("/auth/logout")

    assert csrf_response.headers["Cache-Control"] == "no-store"
    assert identity_response.headers["Cache-Control"] == "no-store"
    assert identity_response.status_code == 401
    assert identity_response.is_json
    assert csrf_error.status_code == 400
    assert csrf_error.is_json
    assert csrf_error.headers["Cache-Control"] == "no-store"
    logout = client.post("/auth/logout", headers=csrf_headers(client))
    assert logout.status_code == 200
    assert logout.headers["Cache-Control"] == "no-store"


def test_oidc_missing_subject_creates_no_user_or_session(
    auth_database: AuthDatabase,
) -> None:
    """Un profil OIDC sans sub est refuse sans persistance d'identite."""
    with pytest.raises(ValueError, match="sujet valide"):
        auth_database.users.sync_external_user("https://issuer.example.test", {})

    assert not auth_database.session.scalars(select(UserLoginState.user_id)).first()
    assert not auth_database.session.scalars(select(UserSession.id)).first()


def test_internal_logout_requires_csrf_and_revokes_session(
    auth_database: AuthDatabase,
) -> None:
    """Le logout exige CSRF et invalide le jeton apres une requete valide."""
    make_internal_user(auth_database)
    client = make_app(auth_database).test_client()
    login = client.post(
        "/auth/login",
        json={"username": "test-user", "password": TEST_PASSWORD},
        headers=csrf_headers(client),
    )
    assert login.status_code == 200
    token = login.get_json()["user"]
    assert token["username"] == "test-user"

    assert client.post("/auth/logout").status_code == 400
    logout = client.post("/auth/logout", headers=csrf_headers(client))
    assert logout.status_code == 200
    assert client.get("/auth/me").status_code == 401
