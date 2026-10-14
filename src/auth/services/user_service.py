"""SQL Operations on authentication users and groups.

.. classes::
    - `UserService` class to manage SQL entities for users and groups.

.. constants::
    - `INITIAL_GROUPS` tuple containing the initial group names.
    - `OIDC_PASSWORD_MARKER` string marker for OIDC users without a password.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

import logging
import hashlib
from datetime import datetime, timezone
from typing import Literal, cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, object_session, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from api.common.db_objects.users import Group as DbGroup
from api.common.db_objects.users import User as DbUser
from api.common.db_objects.users import UserGroup, UserSession
from auth.models import User

INITIAL_GROUPS = ("ADMIN", "EDITOR", "VIEWER")
OIDC_PASSWORD_MARKER = "!oidc-no-password"
LOGGER = logging.getLogger(__name__)

class UserService:
    """Manage SQL entities for users and groups without exposing them to the rest
    of the application.

    :param db_session: Scoped SQLAlchemy session for database interactions.
    :type db_session: scoped_session[Session]

    :raises SQLAlchemyError: If committing the session to the database fails.

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
    """

    def __init__(self, db_session: scoped_session[Session]) -> None:
        """Initialize the UserService with a database session.

        :param db_session: Scoped SQLAlchemy session for database interactions.
        :type db_session: scoped_session[Session]
        """
        self.db_session = db_session

    def ensure_initial_admin(self, username: str, password: str) -> None:
        """Create the initial groups and the administrator if they are missing.
        
        :param username: The username for the initial admin user.
        :type username: str
        :param password: The password for the initial admin user.
        :type password: str
        :raises ValueError: If the username or password is empty.
        """
        if not username.strip() or not password:
            LOGGER.exception("Username or password is empty. Both are required on internal mode.")
            raise ValueError("ADMIN_USERNAME et ADMIN_PASSWORD are required on internal mode")
        session = self.db_session()
        groups = self._ensure_groups(session)
        admin_group = next(group for group in groups if group.name == "ADMIN")
        user = session.scalar(select(DbUser).where(DbUser.username == username))
        if user is None:
            user = DbUser(
                username=username,
                email=f"{username}@localhost",
                hash_password=generate_password_hash(password),
                enabled=True,
                created_at=datetime.now(timezone.utc),
            )
            user.groups = [admin_group]
            session.add(user)
        elif admin_group not in user.groups:
            user.groups.append(admin_group)
        self._commit(session)

    def ensure_groups(self) -> None:
        """Create the missing reference groups.

        :return: None
        :rtype: None

        :raises SQLAlchemyError: If committing the session to the database fails.
        """
        session = self.db_session()
        self._ensure_groups(session)
        self._commit(session)

    def authenticate(self, username: str, password: str) -> User | None:
        """Verify the internal credentials and return a uniform identity.

        :param username: The username of the internal user.
        :type username: str
        :param password: The password of the internal user.
        :type password: str

        :return: The uniform identity if authentication is successful, otherwise None.
        :rtype: User | None
        """
        session = self.db_session()
        record = session.scalar(select(DbUser).where(DbUser.username == username))
        if (
            record is None
            or not record.enabled
            or record.hash_password.startswith("!")
            or not check_password_hash(record.hash_password, password)
        ):
            return None
        record.last_login = datetime.now(timezone.utc)
        self._commit(session)
        return self._to_user(record, "internal")

    def get(self, user_id: int) -> User | None:
        """Return the uniform identity associated with a SQL identifier.

        :param user_id: The SQL identifier of the user.
        :type user_id: int

        :return: The uniform identity if the user exists and is enabled, otherwise None.
        :rtype: User | None

        :raises SQLAlchemyError: If committing the session to the database fails.
        """
        record = self.db_session().get(DbUser, user_id)
        if record is None or not record.enabled:
            LOGGER.debug("User not found or not enabled for user_id: %d", user_id)
            return None
        source = "external" if record.username.startswith("oidc_") else "internal"
        return self._to_user(record, source)

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        group_names: list[str] | None = None,
    ) -> User:
        """Create an internal user with a hashed password.

        Cree un utilisateur interne avec un mot de passe hache.

        :param username: The username of the internal user.
        :type username: str
        :param email: The email of the internal user.
        :type email: str
        :param password: The password of the internal user.
        :type password: str
        :param group_names: The list of group names to assign to the user.
        :type group_names: list[str] | None

        :return: The uniform identity of the created user.
        :rtype: User

        :raises ValueError: If the username, email, or password is empty.
        :raises SQLAlchemyError: If committing the session to the database fails.
        """
        if not username.strip() or not email.strip() or not password:
            LOGGER.exception("Username, email, or password is empty. Cannot create user.")
            raise ValueError("Username, email, or password is empty. Cannot create user.")
        session = self.db_session()
        record = DbUser(
            username=username,
            email=email,
            hash_password=generate_password_hash(password),
            enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        record.groups = self._get_groups(session, group_names or [])
        session.add(record)
        session.flush()
        self._commit(session)
        return self._to_user(record, "internal")

    def update_user(
        self,
        user_id: int,
        *,
        username: str | None = None,
        email: str | None = None,
        password: str | None = None,
        group_names: list[str] | None = None,
        enabled: bool | None = None,
    ) -> User | None:
        """Update only the provided fields.

        :param user_id: The SQL identifier of the user to update.
        :type user_id: int
        :param username: The new username of the user.
        :type username: str | None
        :param email: The new email of the user.
        :type email: str | None
        :param password: The new password of the user.
        :type password: str | None
        :param group_names: The new list of group names to assign to the user.
        :type group_names: list[str] | None
        :param enabled: The new enabled status of the user.
        :type enabled: bool | None

        :return: The uniform identity of the updated user if the user exists, otherwise None.
        :rtype: User | None

        :raises ValueError: If any provided field is invalid.
        :raises SQLAlchemyError: If committing the session to the database fails.
        """
        session = self.db_session()
        record = session.get(DbUser, user_id)
        if record is None:
            return None
        if username is not None:
            if not username.strip():
                LOGGER.exception("Username is empty for user_id: %d", user_id)
                raise ValueError("Le nom d'utilisateur ne peut pas etre vide")
            record.username = username
        if email is not None:
            if not email.strip():
                LOGGER.exception("Email is empty for user_id: %d", user_id)
                raise ValueError("L'email ne peut pas etre vide")
            record.email = email
        if password is not None:
            if not password:
                LOGGER.exception("Password is empty for user_id: %d", user_id)
                raise ValueError("Le mot de passe ne peut pas etre vide")
            record.hash_password = generate_password_hash(password)
        if group_names is not None:
            record.groups = self._get_groups(session, group_names)
        if enabled is not None:
            record.enabled = enabled
        self._commit(session)
        return self._to_user(record, "internal")

    def delete_user(self, user_id: int) -> bool:
        """Delete a user and their persistent sessions.

        :param user_id: The SQL identifier of the user to delete.
        :type user_id: int

        :return: True if the user was deleted, False if the user does not exist.
        :rtype: bool

        :raises SQLAlchemyError: If committing the session to the database fails.
        """
        session = self.db_session()
        record = session.get(DbUser, user_id)
        if record is None:
            return False
        session.execute(delete(UserSession).where(UserSession.user_id == user_id))
        session.delete(record)
        self._commit(session)
        return True

    def list_users(self) -> list[User]:
        """Returns the active users as uniform identities.

        :return: A list of uniform identities representing the active users.
        :rtype: list[User]
        """
        records = self.db_session().scalars(
            select(DbUser).where(DbUser.enabled.is_(True)).order_by(DbUser.id)
        )
        return [self._to_user(record, "internal") for record in records]

    def sync_external_user(self, issuer: str, claims: dict[str, object]) -> User:
        """Persist an OIDC identity and synchronize its authorized groups.

        :param issuer: The OIDC issuer identifier.
        :type issuer: str

        :param claims: The OIDC claims containing user information and groups.
        :type claims: dict[str, object]

        :return: The synchronized user as a uniform identity.
        :rtype: User

        :raises ValueError: If the OIDC response does not contain a valid subject.
        """
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            LOGGER.exception("OIDC response does not contain a valid subject: %s", claims)
            raise ValueError("La reponse OIDC ne contient pas de sujet valide")
        identity = hashlib.sha256(f"{issuer}|{subject}".encode("utf-8")).hexdigest()
        username = f"oidc_{identity[:40]}"
        email = f"{identity}@oidc.invalid"
        raw_groups = claims.get("groups", [])
        requested_groups: set[str] = set()
        if isinstance(raw_groups, list):
            for group in cast(list[object], raw_groups):
                if isinstance(group, str):
                    requested_groups.add(group)
        group_names = requested_groups.intersection(INITIAL_GROUPS)

        session = self.db_session()
        groups = self._ensure_groups(session)
        record = session.scalar(select(DbUser).where(DbUser.username == username))
        if record is None:
            record = DbUser(
                username=username,
                email=email,
                hash_password=OIDC_PASSWORD_MARKER,
                enabled=True,
                created_at=datetime.now(timezone.utc),
            )
            session.add(record)
            session.flush()
        record.groups = [group for group in groups if group.name in group_names]
        self._commit(session)
        return self._to_user(record, "external")

    @staticmethod
    def _ensure_groups(session: Session) -> list[DbGroup]:
        """Ensure that all initial groups exist in the database.

        :param session: The SQLAlchemy session to use for database operations.
        :type session: Session

        :return: A list of all initial groups.
        :rtype: list[DbGroup]
        """
        groups: list[DbGroup] = []
        for name in INITIAL_GROUPS:
            group = session.scalar(select(DbGroup).where(DbGroup.name == name))
            if group is None:
                group = DbGroup(name=name, description=f"GeoReforge {name.lower()} role")
                session.add(group)
            groups.append(group)
        session.flush()
        return groups

    @staticmethod
    def _get_groups(session: Session, names: list[str]) -> list[DbGroup]:
        """Retrieve groups by their names from the database.

        :param session: The SQLAlchemy session to use for database operations.
        :type session: Session

        :param names: A list of group names to retrieve.
        :type names: list[str]

        :return: A list of groups matching the provided names.
        :rtype: list[DbGroup]

        :raises ValueError: If any of the requested groups do not exist.
        """
        if not names:
            return []
        groups = list(session.scalars(select(DbGroup).where(DbGroup.name.in_(set(names)))))
        missing = set(names).difference(group.name for group in groups)
        if missing:
            raise ValueError(f"Groupes inconnus : {', '.join(sorted(missing))}")
        return groups

    @staticmethod
    def _to_user(record: DbUser, source: Literal["internal", "external"]) -> User:
        """Convert a database user record to a uniform user identity.

        :param record: The database user record to convert.
        :type record: DbUser

        :param source: The authentication source of the user, either "internal" or "external".
        :type source: Literal["internal", "external"]

        :return: The user as a uniform identity.
        :rtype: User
        """
        session = object_session(record)
        groups = []
        if session is not None:
            groups = list(
                session.scalars(
                    select(DbGroup.name)
                    .join(UserGroup, UserGroup.group_id == DbGroup.id)
                    .where(UserGroup.user_id == record.id, UserGroup.activated.is_(True))
                ).all()
            )
        return User(
            id=record.id,
            username=record.username,
            groups=groups,
            auth_source=source,
        )

    @staticmethod
    def _commit(session: Session) -> None:
        """Commit the current transaction in the database session.

        :param session: The SQLAlchemy session to use for database operations.
        :type session: Session

        :raises SQLAlchemyError: If the commit fails, the transaction is rolled back and the
        exception is raised.
        """
        try:
            session.commit()
        except SQLAlchemyError as e:
            LOGGER.exception("Failed to commit the transaction: %s", e)
            session.rollback()
            raise SQLAlchemyError("Failed to commit the transaction") from e
