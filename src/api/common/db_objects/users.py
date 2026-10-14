"""
Database objects for users.

.. classes::
    - `User`: Represents a user in the database.
    - `Group`: Represents a group of users in the database.
    - `UserSession`: Represents a session of a user in the database.

.. constant::
    - `__USER_ID`: Description of the unique identifier of the user in the database.

.. author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0
"""
from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

from sqlalchemy import Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base, TABLE_ARGS

__USER_ID = "Unique identifier of the user"

class User(Base):
    """Database object for a user in the database.

    :param id: The unique identifier of the user.
    :type id: int
    :param username: The username of the user.
    :type username: str
    :param email: The email address of the user.
    :type email: str
    :param hash_password: The hashed password of the user.
    :type hash_password: str

    .. methods::
        - **`to_dict(without_secrets: bool = True)`** :
        Converts the User object to a dictionary.
        - **`from_dict(data: dict[str, Any], without_secrets: bool = True)`** :
        Creates a User object from a dictionary.

    .. table:: `users`

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    __tablename__ = "users"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment=__USER_ID,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="Username of the user",
    )
    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="Email address of the user",
    )
    hash_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hashed password of the user",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        unique=False,
        comment="Indicates whether the user is enabled",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        unique=False,
        comment="Timestamp indicating when the user was created",
    )
    last_login: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
        unique=False,
        comment="Timestamp indicating the last login of the user",
    )
    groups: Mapped[list["Group"]] = relationship(
        "Group",
        secondary="user_groups",
        back_populates="users",
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
    )

    def to_dict(self, without_secrets: bool = True) -> dict[str, Any]:
        """Converts the User object to a dictionary.

        :param without_secrets: Whether to exclude sensitive information like the hashed password.
        :type without_secrets: bool
        :return: Dictionary representation of the User object.
        :rtype: dict[str, Any]

        .. notes::
            The `without_secrets` parameter controls whether sensitive information like the
            hashed password is included in the dictionary representation. The default value
            is `True`, meaning sensitive information is excluded by default.

            .. example::

                ```python
                user = User.from_dict({
                    "id": 1,
                    "username": "john_doe",
                    "email": "john@example.com",
                    "hash_password": "hashed_password"
                })
                print(user.to_dict())

                >>> {'id': 1, 'username': 'john_doe', 'email': 'john@example.com'}
                ```
        """
        user_dict = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
        }
        if not without_secrets:
            user_dict["hash_password"] = self.hash_password
        return user_dict

    @classmethod
    def from_dict(cls, data: dict[str, Any], without_secrets: bool = True) -> "User":
        """Creates a User object from a dictionary.

        :param data: Dictionary containing user information.
        :type data: dict[str, Any]
        :param without_secrets: Whether to exclude sensitive information like the hashed password.
        :type without_secrets: bool
        :return: User object created from the dictionary.
        :rtype: User

        .. notes::
            The `without_secrets` parameter controls whether sensitive information like the
            hashed password is expected in the input dictionary. The default value is `True`,
            meaning sensitive information is not expected by default.

            .. example::

                ```python
                data = {
                    "id": 1,
                    "username": "john_doe",
                    "email": "john@example.com",
                    "hash_password": "hashed_password"
                }
                user = User.from_dict(data)
                print(user.to_dict())

                >>> {'id': 1, 'username': 'john_doe', 'email': 'john@example.com'}

                user.hash_password = personalized_hasher("value_of_password")
                ```
        """
        return cls(
            id=data.get("id"),
            username=data.get("username"),
            email=data.get("email"),
            hash_password=data.get("hash_password") if not without_secrets else None,
        )


class Group(Base):
    """Represents a group of users.
    
    :param id: Unique identifier of the group.
    :type id: int
    :param name: Name of the group.
    :type name: str
    :param description: Description of the group.
    :type description: str
    :param users: List of users belonging to the group.
    :type users: list[User]
    
    .. methods::
        - `to_dict()`: Converts the Group object to a dictionary.
        - `from_dict()`: Creates a Group object from a dictionary.
    
    .. table:: `groups`
    
    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    __tablename__ = "groups"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique identifier of the group",
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="Name of the group",
    )
    description: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Description of the group",
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary="user_groups",
        back_populates="groups",
    )


class UserGroup(Base):
    """Represents the association between users and groups.

    :param id: Unique identifier of the user-group association.
    :type id: int
    :param user_id: Unique identifier of the user.
    :type user_id: int
    :param group_id: Unique identifier of the group.
    :type group_id: int
    :param activated: Indicates whether the association between the user and the group is active.
    :type activated: bool

    .. methods::
        - `to_dict()`: Converts the UserGroup object to a dictionary.
        - `from_dict()`: Creates a UserGroup object from a dictionary.

    .. table:: `user_groups`

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    __tablename__ = "user_groups"
    __table_args__ = (UniqueConstraint("user_id", "group_id"), TABLE_ARGS)

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique identifier of the user-group association",
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        comment=__USER_ID,
    )
    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("groups.id"),
        comment="Unique identifier of the group",
    )
    activated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Indicates whether the association between the user and the group is active",
    )


class UserSession(Base):
    """Represents a user session.

    :param id: Unique identifier of the user session.
    :type id: int
    :param user_id: Unique identifier of the user.
    :type user_id: int
    :param session_token: Token representing the user session.
    :type session_token: str
    :param created_at: Timestamp when the session was created.
    :type created_at: datetime
    :param expires_at: Timestamp when the session expires.
    :type expires_at: datetime
    :param user: The user associated with the session.
    :type user: User

    .. methods::
        - `to_dict()`: Converts the UserSession object to a dictionary.
        - `from_dict()`: Creates a UserSession object from a dictionary.

    .. table:: `user_sessions`

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    __tablename__ = "user_sessions"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Unique identifier of the user session",
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        comment=__USER_ID,
    )
    session_token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="Token representing the user session",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        comment="Timestamp when the session was created",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="Timestamp when the session expires",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="sessions",
    )
