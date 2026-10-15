"""Preparation for the additions of TOML, without deletion or modification of the existing content.

"""
# TODO: terminer la documentation
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
    name: str = Field(min_length=1, max_length=100)
    link: str = Field(pattern=r"^[a-z0-9_]+$")
    precision: list[Literal["low", "medium", "high"]] = Field(
        default_factory=lambda: ["high"],
        min_length=1,
        max_length=3,
    )


class _Mapping(BaseModel):
    name: str = Field(min_length=1)
    code: str = Field(min_length=1)
    source_class: str = Field(alias="class", min_length=1)
    classes: dict[str, str] = Field(default_factory=dict)


class _Families(BaseModel):
    cultural: list[_Theme] = Field(default_factory=lambda: cast(list[_Theme], []))
    physical: list[_Theme] = Field(default_factory=lambda: cast(list[_Theme], []))
    raster: list[Any] = Field(default_factory=list)
    mapping: dict[str, _Mapping] = Field(default_factory=dict)


class _Configuration(BaseModel):
    source_path: str
    data_family: _Families


def _fingerprint(kind: str, code: str, name: str, geometry: Any) -> str:
    return sha256(f"{kind}\0{code}\0{name}\0{geometry.normalize().wkb_hex}".encode()).hexdigest()


def _existing(database: Session) -> set[str]:
    return {
        _fingerprint(record.kind, record.code, record.name, read_geometry(record.boundary))
        for record in database.scalars(select(GeographicZone))
    }


def _download(url: str) -> BytesIO:
    address = urlparse(url)
    if address.scheme != "https" \
        or address.hostname != "naturalearth.s3.amazonaws.com" \
        or address.username \
        or address.port:
        raise ValueError("Adresse de source invalide.")
    with requests.get(url, timeout=(10, 60), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Reponse inattendue du serveur de donnees.")
        payload = BytesIO()
        for chunk in response.iter_content(65536):
            payload.write(chunk)
            if payload.tell() > 64 * 1024 * 1024:
                raise ValueError("Le jeu depasse la taille autorisee de 64 Mio.")
    return payload


def _read_entries(url: str, mapper: ZonesMapper) -> list[dict[str, Any]]:
    stem = Path(urlparse(url).path).stem
    mapping_key = next((key for key in mapper.mapping if stem.endswith(f"_{key}")), None)
    if mapping_key is None:
        raise ValueError(f"Mapping absent pour {stem}.")
    fields = mapper.get_mapper(mapping_key)
    if not all(fields.get(key) for key in ("code", "name", "class")):
        raise ValueError(f"Mapping incomplet pour {stem}.")
    classes = mapper.get_classes()
    with ZipFile(_download(url)) as archive:
        components: list[BytesIO] = []
        for extension in ("shp", "shx", "dbf"):
            entry = archive.getinfo(f"{stem}.{extension}")
            if entry.file_size > 128 * 1024 * 1024:
                raise ValueError("Archive trop volumineuse.")
            components.append(BytesIO(archive.read(entry)))
    reader = shapefile.Reader(shp=components[0], shx=components[1], dbf=components[2])
    try:
        return [_mapped_entry(item, fields, classes) for item in reader.iterShapeRecords()]
    finally:
        reader.close()


def _mapped_entry(item: Any, fields: dict[str, str], classes: dict[str, str]) -> dict[str, Any]:
    properties = item.record.as_dict()
    source_kind = str(properties.get(fields["class"], "")).strip()
    kind = str(classes.get(source_kind, source_kind))
    code = str(properties.get(fields["code"], "")).strip()
    name = str(properties.get(fields["name"], "")).strip()
    if not kind or not code or not name or len(kind) > 50 or len(code) > 50 or len(name) > 100:
        raise ValueError("Une entree ne respecte pas le mapping code, nom ou classe.")
    geometry = polygonal(shape(item.shape.__geo_interface__))
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError(f"Geometrie invalide pour {name}.")
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
    """Telecharge les jeux declares et prepare uniquement les nouvelles entrees.

    Args:
        database: Session contenant les sources existantes.
        content: Configuration TOML deposee.
        owner: Identite proprietaire de l'apercu.
        secret: Cle de signature de l'application.

    Returns:
        Jeton signe et liste des ajouts proposes.

    Raises:
        ValueError: Si le document ou un jeu de donnees est invalide.
    """
    try:
        config = _Configuration.model_validate(tomllib.loads(content.decode("utf-8")))
    except (UnicodeError, ValidationError, tomllib.TOMLDecodeError) as error:
        raise ValueError("Le fichier TOML ou sa structure est invalide.") from error
    if config.source_path.rstrip("/") != "https://naturalearth.s3.amazonaws.com":
        raise ValueError("Seule la source HTTPS Natural Earth du catalogue est autorisee.")
    if config.data_family.raster:
        raise ValueError("Les zones sources doivent provenir de jeux vectoriels.")
    known = _existing(database)
    additions: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="georeforge-toml-") as folder:
        config_path = Path(folder) / "zones.toml"
        config_path.write_bytes(content)
        importer = DataImporter(config_path)
        mapper = ZonesMapper(str(config_path))
        if not 1 <= len(importer.data_themes) <= 30:
            raise ValueError("La configuration doit contenir entre un et 30 jeux vectoriels.")
        for theme in importer.data_themes:
            for item in _read_entries(theme.url_route, mapper):
                if item["fingerprint"] not in known:
                    additions.append(item)
                    known.add(item["fingerprint"])
                if len(additions) > 100000:
                    raise ValueError("Trop d'entrees dans un seul import.")
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
    """Applique un apercu signe valide en evitant les doublons deja presents.

    Args:
        database: Session de destination.
        token: Jeton d'apercu signe.
        owner: Identite effectuant la validation.
        secret: Cle de signature de l'application.

    Returns:
        Nombre d'entrees ajoutees.
    """
    payload = URLSafeTimedSerializer(secret, salt="source-preview").loads(token, max_age=1800)
    identifier = payload.get("id", "")
    if (
        payload.get("owner") != owner
        or len(identifier) != 32
        or any(character not in "0123456789abcdef" for character in identifier)
    ):
        raise ValueError("Cet apercu ne vous appartient pas.")
    path = STAGING / f"{identifier}.json"
    if not path.exists():
        raise ValueError("Cet apercu a expire ou a deja ete applique.")
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
