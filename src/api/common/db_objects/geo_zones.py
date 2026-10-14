"""
Module for the `GeographicZone` class representing geographic zones in the database.

.. module:: src.api.common.db_objects.geo_zones

.. class:: GeographicZone: Represents a geographic zone in the database.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0
"""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import mapped_column, Mapped, relationship
from geoalchemy2 import Geometry

from . import Base, TABLE_ARGS

class GeographicZone(Base):
    """
    Database object for geo zones in the database.

    :param id: ID of the geographic zone
    :type id: int
    :param kind: Type of the geographic zone
    :type kind: str
    :param code: Code of the geographic zone
    :type code: str
    :param name: Name of the geographic zone
    :type name: str
    :param boundary: Boundary of the geographic zone
    :type boundary: geoalchemy2.types.Geometry
    :param geo_forged_items: List of forged geographic items associated with the geographic zone
    :type geo_forged_items: list[GeoForgedItem]

    .. methods::
        - `to_dict()`: Converts the GeographicZone object to a dictionary.
        - `from_dict()`: Creates a GeographicZone object from a dictionary.

    .. table:: `geo_zones`

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    __tablename__ = "geo_zones"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=False,
        comment="Type of the geographic zone",
    )
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=False,
        comment="Code of the geographic zone",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=False,
        comment="Name of the geographic zone",
    )
    boundary: Mapped[Geometry] = mapped_column(
        Geometry(
            geometry_type="MULTIPOLYGON",
            srid=4326,
        ),
        nullable=False,
        unique=False,
        comment="Boundary of the geographic zone",
    )
    geo_forged_items = relationship(
        "GeoForgedItem",
        back_populates="geo_zone",
        cascade="all, delete-orphan",
    )
