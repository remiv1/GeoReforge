"""Validate and stage administrative TOML additions of geographic sources.

The preview flow accepts only vector datasets from the curated Natural Earth
HTTPS endpoint. It downloads and validates candidate features without writing
to the database, then stores an owner-bound, signed preview in a private
staging directory. Applying a valid preview adds only sources that are not
already present; it never modifies or deletes existing records.

.. classes::
    - `_Theme`: Validated Natural Earth dataset name, link, and resolutions.
    - `_Mapping`: Validated source-field mapping and class translations.
    - `_Families`: Dataset groups and mappings declared in the TOML file.
    - `_Configuration`: Validated source URL and dataset configuration.

.. functions::
    - `_fingerprint`: Compute a stable fingerprint for a geographic feature.
    - `_existing`: Collect fingerprints of features already in the database.
    - `_download`: Download a bounded archive from the approved Natural Earth host.
    - `_read_entries`: Read and map features from one dataset archive.
    - `_mapped_entry`: Validate and normalize a source feature.
    - `prepare_sources`: Validate TOML and create an owner-bound preview token.
    - `apply_sources`: Add the new entries from a valid preview token.

.. data:: STAGING

    Private temporary directory used to store prepared source previews.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
import tomllib
from typing import Any, Literal, cast
from urllib.parse import urlparse
from uuid import uuid4
from zipfile import ZipFile

from geoalchemy2.shape import from_shape
from itsdangerous import URLSafeTimedSerializer
from pydantic import BaseModel, Field, ValidationError
import requests
import shapefile
from shapely import from_wkt
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common.datas.importer import DataImporter
from ..common.datas.mapper import ZonesMapper
from ..common.db_objects.geo_zones import GeographicZone
from .geometry import polygonal, read_geometry

STAGING = Path(gettempdir()) / "georeforge-previews"


class _Theme(BaseModel):
    """Validate one dataset declaration.

    :param name: Display name of the dataset.
    :type name: str
    :param link: Natural Earth archive name suffix.
    :type link: str
    :param precision: Resolutions to import.
    :type precision: list[Literal["low", "medium", "high"]]

    :raises pydantic.ValidationError: If a field does not match its constraints.
    """

    name: str = Field(min_length=1, max_length=100)
    link: str = Field(pattern=r"^[a-z0-9_]+$")
    precision: list[Literal["low", "medium", "high"]] = Field(
        default_factory=lambda: ["high"],
        min_length=1,
        max_length=3,
    )


class _Mapping(BaseModel):
    """Validate field names and class translations for a dataset.

    :param name: Source field containing the feature name.
    :type name: str
    :param code: Source field containing the feature code.
    :type code: str
    :param source_class: Source field containing the feature class.
    :type source_class: str
    :param classes: Optional translations for source class values.
    :type classes: dict[str, str]

    :raises pydantic.ValidationError: If a field does not match its constraints.
    """

    name: str = Field(min_length=1)
    code: str = Field(min_length=1)
    source_class: str = Field(alias="class", min_length=1)
    classes: dict[str, str] = Field(default_factory=dict)


class _Families(BaseModel):
    """Validate the dataset families and their field mappings.

    :param cultural: Cultural dataset declarations.
    :type cultural: list[_Theme]
    :param physical: Physical dataset declarations.
    :type physical: list[_Theme]
    :param raster: Raster declarations, which are rejected by the preview flow.
    :type raster: list[Any]
    :param mapping: Mapping keyed by Natural Earth dataset link.
    :type mapping: dict[str, _Mapping]

    :raises pydantic.ValidationError: If a family or mapping is invalid.
    """

    cultural: list[_Theme] = Field(default_factory=lambda: cast(list[_Theme], []))
    physical: list[_Theme] = Field(default_factory=lambda: cast(list[_Theme], []))
    raster: list[Any] = Field(default_factory=list)
    mapping: dict[str, _Mapping] = Field(default_factory=dict)


class _Configuration(BaseModel):
    """Validate the top-level TOML source configuration.

    :param source_path: Base URL for the source provider.
    :type source_path: str
    :param data_family: Configured dataset families and mappings.
    :type data_family: _Families

    :raises pydantic.ValidationError: If the configuration is invalid.
    """

    source_path: str
    data_family: _Families


def _fingerprint(kind: str, code: str, name: str, geometry: Any) -> str:
    """Compute a stable fingerprint from feature attributes and normalized geometry.

    :param kind: Normalized feature class.
    :type kind: str
    :param code: Feature code.
    :type code: str
    :param name: Feature name.
    :type name: str
    :param geometry: Shapely geometry to normalize.
    :type geometry: Any

    :return: SHA-256 digest of the feature identity.
    :rtype: str

    :raises AttributeError: If the object does not provide geometry normalization.
    """
    return sha256(f"{kind}\0{code}\0{name}\0{geometry.normalize().wkb_hex}".encode()).hexdigest()


def _existing(database: Session) -> set[str]:
    """Return fingerprints for all geographic zones already in the database.

    :param database: Session used to query existing geographic zones.
    :type database: Session

    :return: Fingerprints of the stored zones.
    :rtype: set[str]

    :raises SQLAlchemyError: If the database query fails.
    """
    return {
        _fingerprint(record.kind, record.code, record.name, read_geometry(record.boundary))
        for record in database.scalars(select(GeographicZone))
    }


def _download(url: str) -> BytesIO:
    """Download a bounded archive from the approved Natural Earth host.

    :param url: HTTPS URL of the source archive.
    :type url: str

    :return: Downloaded archive content.
    :rtype: BytesIO

    :raises ValueError: If the URL, response, or archive size is invalid.
    :raises requests.RequestException: If the HTTP request fails.
    """
    address = urlparse(url)
    if address.scheme != "https" \
        or address.hostname != "naturalearth.s3.amazonaws.com" \
        or address.username \
        or address.port:
        raise ValueError("The source URL is invalid.")
    with requests.get(url, timeout=(10, 60), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("The data provider returned an unexpected response.")
        payload = BytesIO()
        for chunk in response.iter_content(65536):
            payload.write(chunk)
            if payload.tell() > 64 * 1024 * 1024:
                raise ValueError("The dataset exceeds the 64 MiB size limit.")
    return payload


def _read_entries(url: str, mapper: ZonesMapper) -> list[dict[str, Any]]:
    """Read, validate, and map the vector features in one source archive.

    :param url: Download URL for the dataset archive.
    :type url: str
    :param mapper: Mapper containing field and class translations.
    :type mapper: ZonesMapper

    :return: Normalized feature records.
    :rtype: list[dict[str, Any]]

    :raises ValueError: If the mapping or a feature geometry is invalid.
    :raises KeyError: If a required shapefile component is missing from the archive.
    :raises zipfile.BadZipFile: If the downloaded archive is invalid.
    :raises requests.RequestException: If the source archive cannot be downloaded.
    """
    stem = Path(urlparse(url).path).stem
    mapping_key = next((key for key in mapper.mapping if stem.endswith(f"_{key}")), None)
    if mapping_key is None:
        raise ValueError(f"No mapping was found for {stem}.")
    fields = mapper.get_mapper(mapping_key)
    if not all(fields.get(key) for key in ("code", "name", "class")):
        raise ValueError(f"The mapping for {stem} is incomplete.")
    classes = mapper.get_classes()
    with ZipFile(_download(url)) as archive:
        components: list[BytesIO] = []
        for extension in ("shp", "shx", "dbf"):
            entry = archive.getinfo(f"{stem}.{extension}")
            if entry.file_size > 128 * 1024 * 1024:
                raise ValueError("A shapefile component exceeds the allowed size.")
            components.append(BytesIO(archive.read(entry)))
    reader = shapefile.Reader(shp=components[0], shx=components[1], dbf=components[2])
    try:
        return [_mapped_entry(item, fields, classes) for item in reader.iterShapeRecords()]
    finally:
        reader.close()


def _mapped_entry(item: Any, fields: dict[str, str], classes: dict[str, str]) -> dict[str, Any]:
    """Validate and normalize one shapefile feature.

    :param item: Shape record returned by the shapefile reader.
    :type item: Any
    :param fields: Mapping of feature properties to required fields.
    :type fields: dict[str, str]
    :param classes: Translations for source class values.
    :type classes: dict[str, str]

    :return: Normalized feature data with geometry and fingerprint.
    :rtype: dict[str, Any]

    :raises ValueError: If required attributes or geometry are invalid.
    """
    properties = item.record.as_dict()
    source_kind = str(properties.get(fields["class"], "")).strip()
    kind = str(classes.get(source_kind, source_kind))
    code = str(properties.get(fields["code"], "")).strip()
    name = str(properties.get(fields["name"], "")).strip()
    if not kind or not code or not name or len(kind) > 50 or len(code) > 50 or len(name) > 100:
        raise ValueError("A feature does not satisfy the required code, name, or class mapping.")
    geometry = polygonal(shape(item.shape.__geo_interface__))
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError(f"The geometry for {name} is invalid.")
    return {
        "kind": kind,
        "code": code,
        "name": name,
        "wkt": geometry.wkt,
        "fingerprint": _fingerprint(kind, code, name, geometry)
    }


def prepare_sources(
    database: Session,
    content: bytes,
    owner: str,
    secret: str | bytes,
) -> tuple[str, list[dict[str, Any]]]:
    """Download configured datasets and stage only new source features.

    :param database: Session containing existing source zones.
    :type database: Session
    :param content: Uploaded TOML configuration.
    :type content: bytes
    :param owner: Identity that owns the preview.
    :type owner: str
    :param secret: Application key used to sign the preview token.
    :type secret: str | bytes

    :return: Signed preview token and proposed additions.
    :rtype: tuple[str, list[dict[str, Any]]]

    :raises ValueError: If the TOML configuration or a dataset is invalid.
    :raises requests.RequestException: If a source archive cannot be downloaded.
    :raises SQLAlchemyError: If existing zones cannot be queried.
    :raises OSError: If the preview cannot be staged on disk.
    """
    try:
        config = _Configuration.model_validate(tomllib.loads(content.decode("utf-8")))
    except (UnicodeError, ValidationError, tomllib.TOMLDecodeError) as error:
        raise ValueError("The TOML file or its structure is invalid.") from error
    if config.source_path.rstrip("/") != "https://naturalearth.s3.amazonaws.com":
        raise ValueError("Only the curated Natural Earth HTTPS source is allowed.")
    if config.data_family.raster:
        raise ValueError("Source zones must come from vector datasets.")
    known = _existing(database)
    additions: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="georeforge-toml-") as folder:
        config_path = Path(folder) / "zones.toml"
        config_path.write_bytes(content)
        importer = DataImporter(config_path)
        mapper = ZonesMapper(str(config_path))
        if not 1 <= len(importer.data_themes) <= 30:
            raise ValueError("The configuration must contain between 1 and 30 vector datasets.")
        for theme in importer.data_themes:
            for item in _read_entries(theme.url_route, mapper):
                if item["fingerprint"] not in known:
                    additions.append(item)
                    known.add(item["fingerprint"])
                if len(additions) > 100000:
                    raise ValueError("A single import cannot contain more than 100,000 entries.")
    STAGING.mkdir(mode=0o700, parents=True, exist_ok=True)
    identifier = uuid4().hex
    destination = STAGING / f"{identifier}.json"
    destination.write_text(json.dumps(additions), encoding="utf-8")
    destination.chmod(0o600)
    token = URLSafeTimedSerializer(
        secret,
        salt="source-preview",
    ).dumps({"id": identifier, "owner": owner})
    return token, additions


def apply_sources(database: Session, token: str, owner: str, secret: str | bytes) -> int:
    """Apply a valid signed preview without adding duplicate source zones.

    :param database: Destination database session.
    :type database: Session
    :param token: Signed preview token.
    :type token: str
    :param owner: Identity applying the preview.
    :type owner: str
    :param secret: Application key used to verify the preview token.
    :type secret: str | bytes

    :return: Number of source zones added.
    :rtype: int

    :raises itsdangerous.BadSignature: If the token is invalid or expired.
    :raises ValueError: If the preview belongs to another identity or is unavailable.
    :raises SQLAlchemyError: If the source zones cannot be committed.
    :raises OSError: If the staged preview cannot be read or removed.
    """
    payload = URLSafeTimedSerializer(secret, salt="source-preview").loads(token, max_age=1800)
    identifier = payload.get("id", "")
    if (
        payload.get("owner") != owner
        or len(identifier) != 32
        or any(character not in "0123456789abcdef" for character in identifier)
    ):
        raise ValueError("This preview does not belong to the current identity.")
    path = STAGING / f"{identifier}.json"
    if not path.exists():
        raise ValueError("This preview has expired or has already been applied.")
    additions: list[dict[str, str]] = cast(
        list[dict[str, str]], json.loads(path.read_text(encoding="utf-8"))
    )
    known = _existing(database)
    count = 0
    for item in additions:
        geometry: BaseGeometry = from_wkt(item["wkt"])
        fingerprint = _fingerprint(item["kind"], item["code"], item["name"], geometry)
        if fingerprint not in known:
            database.add(
                GeographicZone(
                    kind=item["kind"],
                    code=item["code"],
                    name=item["name"],
                    boundary=from_shape(geometry, srid=4326),
                ),
            )
            known.add(fingerprint)
            count += 1
    database.commit()
    path.unlink(missing_ok=True)
    return count
