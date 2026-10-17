"""User preference and versioned geographic zone services.

.. functions::
    - `preferences`: Retrieve or initialize a user's preferences.
    - `build_zone`: Validate a definition and compose its geometry.
    - `_resolve_source`: Resolve a database-local source identifier.
    - `_validated_steps`: Validate and normalize source operations.
    - `_resolve_manifest_source`: Resolve a source through its import manifest.
    - `_upsert_version_sequence`: Atomically update a version sequence.
    - `advance_version_sequence`: Advance a sequence to a restored version.
    - `restore_snapshot`: Restore one version or a complete catalog snapshot.
    - `_snapshot_content`: Validate a snapshot envelope.
    - `_restore_snapshot_record`: Validate and build a snapshot version.
    - `_restore_snapshot_item`: Validate and build a snapshot operation.
    - `_validate_snapshot_conflicts`: Reject conflicting versions or missing sources.
    - `_snapshot_integer`: Validate an integer from a snapshot.
    - `_reserve_next_version`: Reserve the next catalog version.
    - `delete_zone_version`: Delete one catalog version.
    - `delete_zone_catalog`: Delete every version of a catalog.
    - `save_zone`: Validate and persist a new catalog version.
    - `zone_definition`: Export a portable zone definition.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from geoalchemy2.shape import from_shape
from shapely import from_wkt
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon
from shapely.geometry.base import BaseGeometry
from sqlalchemy import case, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from auth.models import User
from ..common.db_objects.geo_forged import (
    GeoForged,
    GeoForgedItem,
    GeoForgedVersionSequence,
)
from ..common.db_objects.file_import import FileImport, file_import_config_key
from ..common.db_objects.geo_zones import GeographicZone
from ..common.db_objects.users import UserPreferences
from .geometry import OPERATIONS, compose, read_geometry


def preferences(database: Session, user: User) -> UserPreferences:
    """Reads user preferences without implicit writing.

    :param database: Database session.
    :type database: Session
    :param user: User whose preferences are retrieved or initialized.
    :type user: User

    :return: Existing preferences or non-persisted initial values.
    :rtype: UserPreferences

    :raises SQLAlchemyError: If the preference record cannot be retrieved.
    """
    key = f"{user.auth_source}:{user.id}"
    return database.get(UserPreferences, key) or UserPreferences(
        identity_key=key,
        user_id=user.id if isinstance(user.id, int) else None,
        navigation=None,
        theme="system",
    )


def build_zone(
    database: Session,
    definition: Any,
    *,
    require_manifest_sources: bool = False,
) -> tuple[dict[str, Any], MultiPolygon]:
    """Validates a zone definition and computes its ordered operations.

    :param database: Database session containing the sources.
    :type database: Session
    :param definition: Metadata and list of operations.
    :type definition: dict[str, Any]
    :param require_manifest_sources: Reject operations that use database-local source IDs.
    :type require_manifest_sources: bool

    :return: A normalized definition and its composed geometry.
    :rtype: tuple[dict[str, Any], MultiPolygon]

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
    normalized, steps = _validated_steps(
        database,
        definition.get("operations"),
        definition.get("sources", []),
        require_manifest_sources=require_manifest_sources,
    )
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
    except (TypeError, ValueError, GEOSException) as error:
        raise ValueError("Invalid source identifier.") from error
    source = database.get(GeographicZone, source_id)
    if source is None:
        raise ValueError(f"The source {source_id} no longer exists.")
    return source

def _validated_operation(
    database: Session,
    entry: Any,
    sources: list[Any],
    *,
    require_manifest_sources: bool,
) -> tuple[dict[str, Any], tuple[str, BaseGeometry]]:
    """Validate and normalize one source operation.

    :param database: Database session containing the referenced sources.
    :type database: Session
    :param entry: Raw operation entry from the definition.
    :type entry: Any
    :param sources: Manifest declarations from the definition.
    :type sources: list[Any]
    :param require_manifest_sources: Reject database-local source identifiers.
    :type require_manifest_sources: bool

    :return: Normalized operation and its geometry step.
    :rtype: tuple[dict[str, Any], tuple[str, BaseGeometry]]

    :raises ValueError: If the operation or its source reference is invalid.
    """
    if not isinstance(entry, dict):
        raise ValueError("An operation entry is invalid.")
    item = cast(dict[str, Any], entry)
    operation = item.get("operation")
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValueError("The operation type is invalid.")
    if "source" in item:
        source = _resolve_manifest_source(database, item, sources)
    elif require_manifest_sources:
        raise ValueError("Every YAML operation must reference a source manifest.")
    else:
        source = _resolve_source(database, item.get("source_id"))
    return (
        {"operation": operation, "source_id": source.id},
        (operation, read_geometry(source.boundary)),
    )


def _validated_steps(
    database: Session,
    operations: Any,
    sources: Any = None,
    *,
    require_manifest_sources: bool = False,
) -> tuple[list[dict[str, Any]], list[tuple[str, BaseGeometry]]]:
    """Validate and normalize a list of operations for constructing a geographic zone.

    :param database: The SQLAlchemy session to use for database operations.
    :type database: Session
    :param operations: The list of operations to validate and normalize.
    :type operations: Any
    :param sources: The source manifests included in the definition.
    :type sources: Any
    :param require_manifest_sources: Reject operations that use database-local source IDs.
    :type require_manifest_sources: bool

    :return: Normalized operations and their corresponding geometry steps.
    :rtype: tuple[list[dict[str, Any]], list[tuple[str, BaseGeometry]]]

    :raises ValueError: If the operations list is invalid or contains invalid entries.
    """
    if not isinstance(operations, list):
        raise ValueError("A list of operations is required.")
    operations = cast(list[Any], operations)
    if sources is None:
        sources = []
    if not isinstance(sources, list):
        raise ValueError("The source manifest list is invalid.")
    sources = cast(list[Any], sources)
    if not 1 <= len(operations) <= 500:
        raise ValueError("Between one and 500 operations are required.")
    steps: list[tuple[str, BaseGeometry]] = []
    normalized: list[dict[str, Any]] = []
    for entry in operations:
        normalized_operation, geometry_step = _validated_operation(
            database,
            entry,
            sources,
            require_manifest_sources=require_manifest_sources,
        )
        normalized.append(normalized_operation)
        steps.append(geometry_step)
    return normalized, steps


def _find_manifest(sources: list[Any], source_alias: int) -> dict[str, Any]:
    """Find the unique manifest declared for an operation alias.

    :param sources: Manifest declarations from the zone definition.
    :type sources: list[Any]
    :param source_alias: Alias referenced by the operation.
    :type source_alias: int

    :return: The matching manifest declaration.
    :rtype: dict[str, Any]

    :raises ValueError: If the alias is missing or duplicated.
    """
    manifests: list[dict[str, Any]] = []
    for value in sources:
        if isinstance(value, dict):
            manifest_candidate = cast(dict[str, Any], value)
            if manifest_candidate.get("id") == source_alias:
                manifests.append(manifest_candidate)
    if len(manifests) != 1:
        raise ValueError("The source manifest is invalid.")
    return manifests[0]


def _manifest_configuration(manifest: dict[str, Any]) -> dict[str, Any]:
    """Extract and validate the import configuration from a manifest.

    :param manifest: Manifest declaration from the zone definition.
    :type manifest: dict[str, Any]

    :return: Configuration fields used to identify the imported source.
    :rtype: dict[str, Any]

    :raises ValueError: If a required manifest field is missing or invalid.
    """
    keys = ("source_path", "data_family", "name", "precision", "link", "mapping")
    configuration = {key: manifest.get(key) for key in keys}
    text_keys = ("source_path", "data_family", "name", "precision", "link")
    if not all(
        isinstance(configuration[key], str) and configuration[key]
        for key in text_keys
    ) or not isinstance(configuration["mapping"], dict):
        raise ValueError("The source manifest is incomplete.")
    return configuration


def _resolve_manifest_source(
    database: Session,
    operation: dict[str, Any],
    sources: list[Any],
) -> GeographicZone:
    """Resolve a YAML operation through its import manifest and business key.

    :param database: Session containing import manifests and source zones.
    :type database: Session
    :param operation: YAML operation containing the manifest alias, code, and name.
    :type operation: dict[str, Any]
    :param sources: Import manifests declared by the YAML definition.
    :type sources: list[Any]

    :return: The uniquely matching geographic source.
    :rtype: GeographicZone

    :raises ValueError: If the manifest or source is missing, invalid, or ambiguous.
    """
    source_alias = operation.get("source")
    if isinstance(source_alias, bool) or not isinstance(source_alias, int):
        raise ValueError("The source manifest reference is invalid.")
    manifest = _find_manifest(sources, source_alias)
    configuration = _manifest_configuration(manifest)
    config_key = file_import_config_key(configuration)
    file_import = database.scalar(
        select(FileImport).where(FileImport.config_key == config_key)
    )
    if file_import is None:
        raise ValueError("The source described by the YAML has not been imported.")
    source_code = operation.get("code")
    source_name = operation.get("name")
    if not isinstance(source_code, str) or not source_code:
        raise ValueError("The source code is invalid.")
    if not isinstance(source_name, str) or not source_name:
        raise ValueError("The source name is invalid.")
    matches = list(database.scalars(
        select(GeographicZone).where(
            GeographicZone.file_import_id == file_import.id,
            GeographicZone.code == source_code,
            GeographicZone.name == source_name,
        ).limit(2)
    ))
    if len(matches) != 1:
        raise ValueError("The source is missing or ambiguous for this manifest.")
    return matches[0]


def _upsert_version_sequence(
    database: Session,
    code: str,
    candidate: Any,
    *,
    increment_existing: bool,
) -> int:
    """Atomically update the version counter for a catalog code.

    :param database: SQLAlchemy session used for database operations.
    :type database: Session
    :param code: Zone code whose version counter is updated.
    :type code: str
    :param candidate: Candidate version number.
    :type candidate: Any
    :param increment_existing: Whether to increment an existing counter above the candidate.
    :type increment_existing: bool

    :return: Version number after the operation.
    :rtype: int

    :raises ValueError: If the database dialect does not support version allocation.
    :raises RuntimeError: If the version counter could not be updated.
    """
    table: Any = GeoForgedVersionSequence.__table__
    dialect = database.get_bind().dialect.name
    existing = table.c.last_version
    replacement = case(
        (existing < candidate, candidate),
        else_=existing + 1 if increment_existing else existing,
    )

    if dialect == "sqlite":
        statement = sqlite_insert(table).values(code=code, last_version=candidate)
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.code],
            set_={"last_version": replacement},
        ).returning(table.c.last_version)
        return int(database.execute(statement).scalar_one())
    if dialect == "postgresql":
        statement = postgresql_insert(table).values(code=code, last_version=candidate)
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.code],
            set_={"last_version": replacement},
        ).returning(table.c.last_version)
        return int(database.execute(statement).scalar_one())
    if dialect in {"mysql", "mariadb"}:
        statement = mysql_insert(table).values(code=code, last_version=candidate)
        database.execute(statement.on_duplicate_key_update(last_version=replacement))
        version = database.scalar(select(table.c.last_version).where(table.c.code == code))
        if version is None:
            raise RuntimeError("The version counter was not updated.")
        return int(version)
    raise ValueError(f"The database dialect {dialect} does not support version allocation.")


def advance_version_sequence(database: Session, code: str, version: int) -> None:
    """Keep a zone's version sequence at least as high as a restored version.

    :param database: The database session to use for the operation.
    :type database: Session
    :param code: The code of the zone whose version sequence is to be advanced.
    :type code: str
    :param version: The version number to advance the sequence to.
    :type version: int

    :return: None
    :rtype: None

    :raises ValueError: If the database dialect does not support version allocation.
    :raises RuntimeError: If the version counter could not be updated.
    """
    _upsert_version_sequence(
        database,
        code,
        version,
        increment_existing=False,
    )


def restore_snapshot(database: Session, payload: Any) -> list[GeoForged]:
    """Restore a version or complete catalog from a validated YAML snapshot.

    :param database: The database session to use for the operation.
    :type database: Session
    :param payload: The validated YAML snapshot payload.
    :type payload: Any

    :return: A list of restored GeoForged records.
    :rtype: list[GeoForged]

    :raises ValueError: If the snapshot is invalid or conflicts with existing data.
    """
    kind, code, records_data = _snapshot_content(payload)
    if kind == "version" and len(records_data) != 1:
        raise ValueError("A version snapshot must contain exactly one version.")
    restored = [_restore_snapshot_record(values, code) for values in records_data]
    advance_version_sequence(database, code, max(record.version for record in restored))
    database.scalar(
        select(GeoForgedVersionSequence)
        .where(GeoForgedVersionSequence.code == code)
        .with_for_update()
    )
    _validate_snapshot_conflicts(database, code, restored)
    database.add_all(restored)
    database.flush()
    return restored


def _snapshot_content(payload: Any) -> tuple[str, str, list[Any]]:
    """Validate the snapshot envelope and return its record data.

    :param payload: The validated YAML snapshot payload.
    :type payload: Any

    :return: A tuple containing the kind of snapshot, the catalog code, and the list of record data.
    :rtype: tuple[str, str, list[Any]]

    :raises ValueError: If the snapshot envelope is invalid.
    """
    if not isinstance(payload, dict):
        raise ValueError("The file isn't a GeoReforge snapshot.")
    payload = cast(dict[str, Any], payload)
    snapshot = payload.get("_georeforge_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("The GeoReforge snapshot is missing.")
    snapshot = cast(dict[str, Any], snapshot)
    if snapshot.get("format") != "georeforge-snapshot" or snapshot.get("format_version") != 1:
        raise ValueError("The snapshot format version is not supported.")
    kind = snapshot.get("kind")
    records_data = snapshot.get("records")
    code = snapshot.get("code")
    if kind not in {"version", "catalog"} or not isinstance(code, str):
        raise ValueError("The snapshot metadata is invalid.")
    if not isinstance(records_data, list) or not records_data:
        raise ValueError("The snapshot contains no records.")
    return cast(str, kind), code, cast(list[Any], records_data)


def _restore_snapshot_record(values: Any, code: str) -> GeoForged:
    """Validate and build one version from snapshot data.

    :param values: The record data for the version.
    :type values: Any
    :param code: The catalog code to which the version belongs.
    :type code: str

    :return: The restored GeoForged version object.
    :rtype: GeoForged

    :raises ValueError: If the snapshot record is invalid.
    """
    if not isinstance(values, dict):
        raise ValueError("A snapshot record is not a dictionary.")
    values = cast(dict[str, Any], values)
    if values.get("code") != code:
        raise ValueError("A snapshot record does not match the catalog.")
    snapshot_id = _snapshot_integer(values.get("id"), "Version ID")
    version = _snapshot_integer(values.get("version"), "Version number")
    name = values.get("name")
    description = values.get("description", "")
    author = values.get("author")
    if (
        not code.strip() or len(code) > 50
        or not isinstance(name, str) or not name.strip() or len(name) > 100
        or not isinstance(description, str) or len(description) > 255
        or not isinstance(author, str) or not author.strip() or len(author) > 100
    ):
        raise ValueError("The metadata of a snapshot version is invalid.")
    try:
        from_date = date.fromisoformat(str(values.get("from_date", "")))
        geometry = from_wkt(str(values.get("geometry", "")))
    except (TypeError, ValueError, GEOSException) as error:
        raise ValueError("The date or geometry of the snapshot is invalid.") from error
    if not isinstance(geometry, MultiPolygon) or geometry.is_empty or not geometry.is_valid:
        raise ValueError("The geometry of the snapshot must be a valid multipolygon.")
    items_data = values.get("items")
    if not isinstance(items_data, list):
        raise ValueError("Each version must contain between one and 500 operations.")
    items_data = cast(list[Any], items_data)
    if not 1 <= len(items_data) <= 500:
        raise ValueError("Each version must contain between one and 500 operations.")
    items = [
        _restore_snapshot_item(item, snapshot_id)
        for item in items_data
    ]
    if len({item.rank for item in items}) != len(items):
        raise ValueError("The operation ranks of the snapshot are duplicated.")
    if min(items, key=lambda item: item.rank).operation != "UNION":
        raise ValueError("The first operation of a version must be a union.")
    return GeoForged(
        code=code,
        name=name,
        description=description,
        version=version,
        from_date=from_date,
        author=author,
        geometry=from_shape(geometry, srid=4326),
        items=items,
    )


def _restore_snapshot_item(values: Any, snapshot_parent_id: int) -> GeoForgedItem:
    """Validate and build one operation from snapshot data.

    :param values: The raw snapshot operation data.
    :type values: Any
    :param snapshot_parent_id: The ID of the parent snapshot version.
    :type snapshot_parent_id: int

    :return: A validated snapshot operation.
    :rtype: GeoForgedItem

    :raises ValueError: If the snapshot operation is invalid.
    """
    if not isinstance(values, dict):
        raise ValueError("A snapshot operation is not a dictionary.")
    values = cast(dict[str, Any], values)
    _snapshot_integer(values.get("id"), "Operation ID")
    linked_id = _snapshot_integer(values.get("geo_forged_id"), "Linked version ID")
    source_id = _snapshot_integer(values.get("geo_zone_id"), "Source ID")
    rank = _snapshot_integer(values.get("rank"), "Operation rank", minimum=0)
    operation = values.get("operation")
    if (
        linked_id != snapshot_parent_id
        or not isinstance(operation, str)
        or operation not in OPERATIONS
    ):
        raise ValueError("The snapshot operation is inconsistent.")
    return GeoForgedItem(
        geo_zone_id=source_id,
        rank=rank,
        operation=operation,
    )


def _validate_snapshot_conflicts(
    database: Session,
    code: str,
    records: list[GeoForged],
) -> None:
    """Reject conflicted versions and missing sources before writing.

    :param database: The database session.
    :type database: Session
    :param code: The code of the catalog.
    :type code: str
    :param records: The list of GeoForged records to validate.
    :type records: list[GeoForged]

    :return: None.
    :rtype: None

    :raises ValueError: If there are conflicts or missing sources in the snapshot.
    """
    versions = [record.version for record in records]
    items = [item for record in records for item in record.items]
    source_ids = {item.geo_zone_id for item in items}
    if len(set(versions)) != len(versions):
        raise ValueError("The snapshot contains a duplicate version number.")
    if database.scalar(
        select(GeoForged.id).where(
            GeoForged.code == code,
            GeoForged.version.in_(versions),
        ).limit(1)
    ):
        raise ValueError("One of the snapshot versions already exists in this catalog.")
    existing_sources = set(database.scalars(
        select(GeographicZone.id).where(GeographicZone.id.in_(source_ids))
    ))
    if existing_sources != source_ids:
        raise ValueError("A source referenced by the snapshot no longer exists.")


def _snapshot_integer(value: Any, label: str, *, minimum: int = 1) -> int:
    """Validate an integer stored in a YAML snapshot.

    :param value: The value to validate.
    :type value: Any
    :param label: The label for the value, used in error messages.
    :type label: str
    :param minimum: The minimum acceptable value (default is 1).
    :type minimum: int

    :return: The validated integer.
    :rtype: int

    :raises ValueError: If the value is not a valid integer or is below the minimum.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"`{label}` is invalid in the snapshot.")
    return value


def _reserve_next_version(database: Session, code: str) -> int:
    """Reserve the next version number for a given catalog code.

    :param database: The database session.
    :type database: Session
    :param code: The code of the catalog.
    :type code: str

    :return: The next reserved version number.
    :rtype: int

    :raises ValueError: If the database dialect does not support version allocation.
    :raises RuntimeError: If the version counter could not be updated.
    """
    maximum = (
        select(func.max(GeoForged.version))
        .where(GeoForged.code == code)
        .scalar_subquery()
    )
    return _upsert_version_sequence(
        database,
        code,
        func.coalesce(maximum, 0) + 1,
        increment_existing=True,
    )


def delete_zone_version(database: Session, identifier: int) -> None:
    """Delete one version while retaining its catalog's version counter.

    :param database: The database session.
    :type database: Session
    :param identifier: The identifier of the version to delete.
    :type identifier: int

    :return: None.
    :rtype: None

    :raises ValueError: If the version does not exist.
    """
    record = database.get(GeoForged, identifier)
    if record is None:
        raise ValueError("This version does not exist.")
    code = record.code
    advance_version_sequence(database, code, record.version)
    database.scalar(
        select(GeoForgedVersionSequence)
        .where(GeoForgedVersionSequence.code == code)
        .with_for_update()
    )
    database.delete(record)
    database.commit()


def delete_zone_catalog(database: Session, code: str) -> int:
    """Delete every version for a code while preserving its sequence counter.

    :param database: The database session.
    :type database: Session
    :param code: The code of the catalog to delete.
    :type code: str

    :return: The number of deleted versions.
    :rtype: int

    :raises ValueError: If the catalog has no remaining versions.
    """
    maximum = database.scalar(
        select(func.max(GeoForged.version)).where(GeoForged.code == code)
    )
    if maximum is None:
        raise ValueError("This catalog contains no more versions.")
    advance_version_sequence(database, code, maximum)
    database.scalar(
        select(GeoForgedVersionSequence)
        .where(GeoForgedVersionSequence.code == code)
        .with_for_update()
    )
    records = list(database.scalars(
        select(GeoForged)
        .where(GeoForged.code == code)
        .with_for_update()
    ))
    for record in records:
        database.delete(record)
    database.commit()
    return len(records)


def save_zone(
    database: Session,
    definition: dict[str, Any],
    user: User,
    *,
    require_manifest_sources: bool = False,
) -> GeoForged:
    """Save a new version without modifying existing versions.

    :param database: Database session.
    :type database: Session
    :param definition: Definition to validate.
    :type definition: dict[str, Any]
    :param user: Author of the version.
    :type user: User
    :param require_manifest_sources: Reject operations that use database-local source IDs.
    :type require_manifest_sources: bool

    :return: New persisted version.
    :rtype: GeoForged

    :raises ValueError: If the definition or any source reference is invalid.
    :raises SQLAlchemyError: If the version cannot be persisted.
    """
    values, geometry = build_zone(
        database,
        definition,
        require_manifest_sources=require_manifest_sources,
    )
    record = GeoForged(
        code=values["code"], name=values["name"], description=values["description"],
        from_date=date.fromisoformat(values["from_date"]), author=user.username,
        version=_reserve_next_version(database, values["code"]),
        geometry=from_shape(geometry, srid=4326),
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

    :return: A portable definition without database-local IDs or version metadata.
    :rtype: dict[str, Any]
    """
    source_aliases: dict[int, int] = {}
    sources: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []
    for item in sorted(record.items, key=lambda item: item.rank):
        zone = item.geo_zone
        file_import = zone.file_import
        if file_import is None:
            operations.append({"operation": item.operation, "source_id": item.geo_zone_id})
            continue
        alias = source_aliases.get(file_import.id)
        if alias is None:
            alias = len(sources)
            source_aliases[file_import.id] = alias
            sources.append({
                "id": alias,
                "source_path": file_import.source_path,
                "data_family": file_import.data_family,
                "name": file_import.name,
                "precision": file_import.precision,
                "link": file_import.link,
                "mapping": file_import.mapping,
            })
        operations.append({
            "operation": item.operation,
            "source": alias,
            "code": zone.code,
            "name": zone.name,
        })
    definition = {
        "code": record.code, "name": record.name, "description": record.description or "",
        "from_date": record.from_date.isoformat(),
        "operations": operations,
    }
    if sources:
        definition["sources"] = sources
    return definition
