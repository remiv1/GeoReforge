"""Persisted manifests for geographic data imports.

.. classes::
    - `FileImport`: Stores the configuration used to import a geographic source.

.. functions::
    - `file_import_config_key`: Build a deterministic key from a normalized import config.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base, TABLE_ARGS

if TYPE_CHECKING:
    from .geo_zones import GeographicZone


def file_import_config_key(configuration: dict[str, Any]) -> str:
    """Build a deterministic key for a normalized import configuration.

    :param configuration: Normalized source configuration, including its mapping.
    :type configuration: dict[str, Any]

    :return: SHA-256 hexadecimal digest of the canonical JSON configuration.
    :rtype: str

    :raises TypeError: If the configuration contains a value that cannot be encoded as JSON.
    """
    payload = json.dumps(
        configuration,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


class FileImport(Base):
    """Persisted configuration for one geographic data import.

    :param config_key: Deterministic key for the normalized configuration.
    :type config_key: str
    :param source_path: Base URL of the source provider.
    :type source_path: str
    :param data_family: Source family, such as cultural or physical.
    :type data_family: str
    :param name: Human-readable dataset name.
    :type name: str
    :param precision: Dataset resolution from the configuration.
    :type precision: str
    :param link: Dataset URL suffix.
    :type link: str
    :param mapping: Source column and class mappings.
    :type mapping: dict[str, Any]
    :param geo_zones: Geographic zones imported from this configuration.
    :type geo_zones: list[GeographicZone]

    .. table:: file_import

    .. methods::
        - `__init__`: Initialize a persisted import manifest.

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
    """

    __tablename__ = "file_import"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Primary key for the file_import table."
    )
    config_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="Deterministic key for the normalized configuration."
    )
    source_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Base URL of the source provider."
    )
    data_family: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Source family, such as cultural or physical."
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Human-readable dataset name."
    )
    precision: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Dataset resolution from the configuration."
    )
    link: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Dataset URL suffix."
    )
    mapping: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Source column and class mappings."
    )

    geo_zones: Mapped[list["GeographicZone"]] = relationship(
        back_populates="file_import",
    )
