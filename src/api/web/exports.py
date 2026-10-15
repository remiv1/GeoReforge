"""Exports constructed zones in GIS formats.

.. functions::
    - `vector_archive`: Produces an in-memory GeoPackage or Shapefile archive.
    - `export_zone`: Exports a constructed zone in the specified format.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""

from __future__ import annotations

from io import BytesIO
import json
from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import fiona
from fiona.io import MemoryFile
from shapely.geometry.base import BaseGeometry
import yaml

from ..common.db_objects.geo_forged import GeoForged
from .geometry import feature, read_geometry
from .services import zone_definition


def vector_archive(geometry: BaseGeometry, code: str, driver: str) -> bytes:
    """Produces an in-memory GeoPackage or Shapefile archive.

    :param geometry: Surface to be exported.
    :type geometry: BaseGeometry
    :param code: Zone code.
    :type code: str
    :param driver: Fiona driver used.
    :type driver: str

    :return: Binary content of the export.
    :rtype: bytes
    """
    schema = {"geometry": "MultiPolygon", "properties": {"code": "str"}}
    if driver == "GPKG":
        with MemoryFile() as memory:
            with cast(Any, memory).open(
                driver=driver,
                schema=schema,
                crs="EPSG:4326",
                layer="zones",
            ) as collection:
                collection.write(feature(geometry, code=code))
            return cast(bytes, cast(Any, memory).read())

    with TemporaryDirectory(prefix="georeforge-export-") as folder:
        destination = Path(folder) / "zone.shp"
        with cast(Any, fiona).open(
            destination,
            "w",
            driver="ESRI Shapefile",
            schema=schema,
            crs="EPSG:4326",
            encoding="UTF-8",
        ) as collection:
            collection.write(feature(geometry, code=code))
        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            for component in Path(folder).iterdir():
                archive.write(component, component.name)
        return output.getvalue()


def export_zone(record: GeoForged, format_name: str) -> tuple[bytes, str, str]:
    """Exports a version without accessing a destination database.

    :param record: Version to be exported.
    :type record: GeoForged
    :param format_name: Format chosen by the user.
    :type format_name: str

    :return: Content, MIME type, and extension.
    :rtype: tuple[bytes, str, str]

    :raises ValueError: If the format is unknown.
    """
    if format_name == "yaml":
        return yaml.safe_dump(
            zone_definition(record),
            allow_unicode=True,
            sort_keys=False,
        ).encode(), "application/yaml", "yaml"
    geometry = read_geometry(record.geometry)
    if format_name == "geojson":
        content = {
            "type": "FeatureCollection",
            "features": [
                feature(
                    geometry,
                    code=record.code,
                    name=record.name,
                    version=record.version,
                ),
            ],
        }
        return json.dumps(content, ensure_ascii=False).encode(), "application/geo+json", "geojson"
    if format_name == "gpkg":
        return vector_archive(
            geometry,
            record.code,
            "GPKG",
        ), "application/geopackage+sqlite3", "gpkg"
    if format_name == "shp":
        return vector_archive(
            geometry,
            record.code,
            "ESRI Shapefile",
        ), "application/zip", "zip"
    if format_name == "postgis":
        code = record.code.replace("'", "''")
        content = (
            "BEGIN;\nCREATE TABLE IF NOT EXISTS georeforge_export "
            "(code text, version integer, geometry geometry(MultiPolygon,4326));\n"
            f"INSERT INTO georeforge_export VALUES ('{code}', {int(record.version)}, "
            f"ST_GeomFromEWKT('SRID=4326;{geometry.wkt}'));\nCOMMIT;\n"
        )
        return content.encode(), "application/sql", "sql"
    raise ValueError("Format d'export inconnu.")
