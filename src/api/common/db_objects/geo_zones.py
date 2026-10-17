"""Database model for imported geographic zones.

.. module:: src.api.common.db_objects.geo_zones

.. classes::
    - `GeographicZone`: Represents one imported geographic zone.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import mapped_column, Mapped, relationship
from geoalchemy2 import Geometry

from . import Base, TABLE_ARGS, foreign_key_target, table_key

if TYPE_CHECKING:
    from .file_import import FileImport
    from .geo_forged import GeoForged

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
    :param file_import_id: ID of the import manifest, when the zone has one.
    :type file_import_id: int | None
    :param file_import: Import manifest associated with the zone.
    :type file_import: FileImport | None
    :param geo_forged_items: List of forged geographic items associated with the geographic zone
    :type geo_forged_items: list[GeoForgedItem]
    :param geo_forged: Constructed zones that reference this source.
    :type geo_forged: list[GeoForged]

    .. methods::
        - `to_dict()`: Converts the GeographicZone object to a dictionary.
        - `from_dict()`: Creates a GeographicZone object from a dictionary.

    .. table:: `geo_zones`

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
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
    file_import_id: Mapped[int | None] = mapped_column(
        ForeignKey(foreign_key_target("file_import")),
        nullable=True,
    )
    file_import: Mapped["FileImport | None"] = relationship(
        back_populates="geo_zones",
    )
    geo_forged_items = relationship(
        "GeoForgedItem",
        back_populates="geo_zone",
        cascade="all, delete-orphan",
    )
    geo_forged: Mapped[list["GeoForged"]] = relationship(
        "GeoForged",
        secondary=lambda: Base.metadata.tables[table_key("geo_forged_item")],
        back_populates="geo_zones",
        viewonly=True,
    )
