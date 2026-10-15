"""Geometrical calculations shared by the constructor and comparisons.

.. functions::
    - `read_geometry()`: Converts a SQLAlchemy geometry to a Shapely geometry.
    - `polygonal()`: Retains only the polygonal components of a geometry.
    - `compose()`: Applies a sequence of spatial operations.
    - `feature()`: Constructs a GeoJSON feature from a geometry.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from geoalchemy2.elements import WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from shapely import from_wkt
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping
from shapely.geometry.base import BaseGeometry

OPERATIONS = {
    "UNION": "Ajout",
    "DIFFERENCE": "Retrait",
    "INTERSECTION": "Intersection",
    "EXCLUDE": "Exclusion",
}


def read_geometry(value: Any) -> BaseGeometry:
    """Converts a SQLAlchemy geometry to a Shapely geometry.

    :param value: Spatial geometry stored in the database.
    :type value: Any

    :return: Corresponding Shapely geometry.
    :rtype: BaseGeometry
    """
    if isinstance(value, BaseGeometry):
        return value
    if isinstance(value, WKTElement):
        return from_wkt(str(value).split(";", 1)[-1])
    if isinstance(value, WKBElement):
        return to_shape(value)
    raise ValueError("La geometrie n'est pas disponible.")


def polygonal(geometry: BaseGeometry) -> MultiPolygon:
    """Retains only the polygonal components of a geometry result.

    :param geometry: Result of a spatial operation.
    :type geometry: BaseGeometry

    :return: Multipolygon, possibly empty.
    :rtype: MultiPolygon
    """
    if isinstance(geometry, Polygon):
        return MultiPolygon([geometry])
    if isinstance(geometry, MultiPolygon):
        return geometry
    if isinstance(geometry, GeometryCollection):
        return MultiPolygon([
            polygon
            for part in cast("GeometryCollection[BaseGeometry]", geometry).geoms
            for polygon in polygonal(part).geoms
        ])
    return MultiPolygon([])


def compose(steps: Iterable[tuple[str, BaseGeometry]]) -> MultiPolygon:
    """Applies the operations in their declared order.

    :param steps: Pairs of operation and source geometry.
    :type steps: Iterable[tuple[str, BaseGeometry]]

    :return: Multipolygon result of the operations.
    :rtype: MultiPolygon

    :raises ValueError: If an operation or source is invalid.
    """
    result: BaseGeometry = MultiPolygon([])
    for operation, source in steps:
        if operation not in OPERATIONS:
            raise ValueError("Operation inconnue.")
        if not source.is_valid:
            raise ValueError("Une source contient une geometrie invalide.")
        if operation == "UNION":
            result = result.union(source)
        elif operation == "DIFFERENCE":
            result = result.difference(source)
        elif operation == "INTERSECTION":
            result = result.intersection(source)
        else:
            result = result.symmetric_difference(source)
    return polygonal(result)


def feature(geometry: BaseGeometry, **properties: Any) -> dict[str, Any]:
    """Constructs a GeoJSON feature from a geometry.

    :param geometry: Geometry to serialize.
    :type geometry: BaseGeometry
    :param **properties: Attributes of the feature.

    :return: GeoJSON feature.
    :rtype: dict[str, Any]
    """
    return {"type": "Feature", "geometry": mapping(geometry), "properties": properties}
