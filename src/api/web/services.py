"""Preferences services and versioned zone construction services.

.. functions::
   - `preferences`: Reads user preferences.
   - `build_zone`: Validates a zone definition and computes its ordered operations.
   - `save_zone`: Saves a new version of a zone without modifying existing versions.
   - `_resolve_source`: Resolves a source identifier to a `GeographicZone` instance.
   - `zone_definition`: Retrieves the normalized definition and final geometry of a zone.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon
from shapely.geometry.base import BaseGeometry
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth.models import User
from ..common.db_objects.geo_forged import GeoForged, GeoForgedItem
from ..common.db_objects.geo_zones import GeographicZone
from ..common.db_objects.users import UserPreferences
from .geometry import OPERATIONS, compose, read_geometry


def preferences(database: Session, user: User) -> UserPreferences:
    """Reads user preferences without implicit writing.

    :param database: Database session.
    :type database: Session
    :type user: User

    :return: Existing preferences or non-persisted initial values.
    :rtype: UserPreferences
    """
    key = f"{user.auth_source}:{user.id}"
    return database.get(UserPreferences, key) or UserPreferences(
        identity_key=key,
        user_id=user.id if isinstance(user.id, int) else None,
        navigation=None,
        theme="system",
    )


def build_zone(database: Session, definition: Any) -> tuple[dict[str, Any], MultiPolygon]:
    """Validates a zone definition and computes its ordered operations.

    :param database: Database session containing the sources.
    :type database: Session
    :param definition: Metadata and list of operations.
    :type definition: dict[str, Any]

    :return: Normalized definition and final geometry.

    :raises ValueError: If the definition or a source is invalid.
    """
    if not isinstance(definition, dict):
        raise ValueError("The definition must be a YAML file.")
    definition = cast(dict[str, Any], definition)
    code = str(definition.get("code", "")).strip()
    name = str(definition.get("name", "")).strip()
    description = str(definition.get("description", "")).strip()
    if not code or len(code) > 50 or not name or len(name) > 100 or len(description) > 255:
        raise ValueError("Code, name or description missing or too long.")
    try:
        start = date.fromisoformat(str(definition.get("from_date", date.today())))
    except ValueError as error:
        raise ValueError("The start date is invalid.") from error
    normalized, steps = _validated_steps(database, definition.get("operations"))
    if normalized[0]["operation"] != "UNION":
        raise ValueError("The first operation must be an addition.")
    geometry = compose(steps)
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError("The construction must produce a valid non-empty surface.")
    return {
        "code": code, "name": name, "description": description,
        "from_date": start.isoformat(), "operations": normalized,
    }, geometry


def _resolve_source(database: Session, identifier: Any) -> GeographicZone:
    """Resolve a source by its identifier from the database.

    :param database: The SQLAlchemy session to use for database operations.
    :type database: Session
    :param identifier: The identifier of the source to resolve.
    :type identifier: Any

    :return: The resolved geographic zone.
    :rtype: GeographicZone

    :raises ValueError: If the identifier is invalid or the source does not exist.
    """
    try:
        source_id = int(identifier)
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid source identifier.") from error
    source = database.get(GeographicZone, source_id)
    if source is None:
        raise ValueError(f"The source {source_id} no longer exists.")
    return source

def _validated_steps(
        database: Session,
        operations: Any
    ) -> tuple[list[dict[str, Any]], list[tuple[str, BaseGeometry]]]:
    """Validate and normalize a list of operations for constructing a geographic zone.

    :param database: The SQLAlchemy session to use for database operations.
    :type database: Session
    :param operations: The list of operations to validate and normalize.
    :type operations: Any

    :return: A tuple containing the normalized operations and the corresponding geometry steps.
    :rtype: tuple[list[dict[str, Any]], list[tuple[str, BaseGeometry]]]

    :raises ValueError: If the operations list is invalid or contains invalid entries.
    """
    if not isinstance(operations, list):
        raise ValueError("Une liste d'operations est requise.")
    operations = cast(list[Any], operations)
    if not 1 <= len(operations) <= 500:
        raise ValueError("Entre une et 500 operations sont requises.")
    steps: list[tuple[str, BaseGeometry]] = []
    normalized: list[dict[str, Any]] = []
    for entry in operations:
        if not isinstance(entry, dict):
            raise ValueError("Operation invalide.")
        item = cast(dict[str, Any], entry)
        if not isinstance(item.get("operation"), str) or item["operation"] not in OPERATIONS:
            raise ValueError("Operation invalide.")
        source = _resolve_source(database, item.get("source_id"))
        normalized.append({"operation": item["operation"], "source_id": source.id})
        steps.append((item["operation"], read_geometry(source.boundary)))
    return normalized, steps

def save_zone(database: Session, definition: dict[str, Any], user: User) -> GeoForged:
    """Save a new version without modifying existing versions.

    :param database: Database session.
    :type database: Session
    :param definition: Definition to validate.
    :type definition: dict[str, Any]
    :param user: Author of the version.
    :type user: User

    :return: New persisted version.
    :rtype: GeoForged
    """
    values, geometry = build_zone(database, definition)
    database.execute(select(GeoForged.id).where(GeoForged.code == values["code"]).with_for_update())
    latest = database.scalar(
        select(func.max(GeoForged.version)).where(GeoForged.code == values["code"])
    ) or 0
    record = GeoForged(
        code=values["code"], name=values["name"], description=values["description"],
        from_date=date.fromisoformat(values["from_date"]), author=user.username,
        version=latest + 1, geometry=from_shape(geometry, srid=4326),
    )
    record.items = [
        GeoForgedItem(rank=rank, operation=item["operation"], geo_zone_id=item["source_id"])
        for rank, item in enumerate(values["operations"])
    ]
    database.add(record)
    database.commit()
    return record


def zone_definition(record: GeoForged) -> dict[str, Any]:
    """Expose a reproducible definition for the editor and YAML export.

    :param record: Version of a constructed zone.
    :type record: GeoForged

    :return: Definition sans identifiant ni version imposes a l'import.
    :rtype: dict[str, Any]
    """
    return {
        "code": record.code, "name": record.name, "description": record.description or "",
        "from_date": record.from_date.isoformat(),
        "operations": [
            {"operation": item.operation, "source_id": item.geo_zone_id}
            for item in sorted(record.items, key=lambda item: item.rank)
        ],
    }
