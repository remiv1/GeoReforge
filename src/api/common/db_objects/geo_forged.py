"""Module for the `GeoForged` class representing forged geographic entities in the database.

.. module: src.api.common.db_objects.geo_forged

.. classes::
    - `GeoForged`: Represents a forged geographic entity in the database.
    - `GeoForgedItem`: Represents an item associated with a forged geographic entity.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, Date, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from . import Base, TABLE_ARGS, foreign_key_target, table_key

if TYPE_CHECKING:
    from .geo_zones import GeographicZone

class GeoForged(Base):
    """Represents a forged geographic entity in the database.

    :param id: ID of the forged geographic entity
    :type id: int
    :param code: Code of the forged geographic entity
    :type code: str
    :param name: Name of the forged geographic entity
    :type name: str
    :param description: Description of the forged geographic entity
    :type description: str
    :param version: Version of the forged geographic entity
    :type version: int
    :param from_date: Start date of the forged geographic entity
    :type from_date: datetime.date
    :param author: Author of the forged geographic entity
    :type author: str
    :param geometry: Geometry of the forged geographic entity
    :type geometry: geoalchemy2.types.Geometry
    :param items: List of items associated with the forged geographic entity
    :type items: list[GeoForgedItem]
    :param geo_zones: List of geographic zones associated with the forged geographic entity
    :type geo_zones: list[GeographicZone]

    .. methods::
        - `to_dict()`: Converts the GeoForged object to a dictionary.
        - `from_dict()`: Creates a GeoForged object from a dictionary.

    .. table:: `geo_forged`

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    __tablename__ = "geo_forged"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="ID of the forged geographic entity",
    )
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=False,
        comment="Code of the forged geographic entity",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=False,
        comment="Name of the forged geographic entity",
    )
    description: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        unique=False,
        comment="Description of the forged geographic entity",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=False,
        comment="Version of the forged geographic entity",
    )
    from_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        unique=False,
        comment="Start date of the forged geographic entity",
    )
    author: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=False,
        comment="Author of the forged geographic entity",
    )
    geometry: Mapped[Geometry] = mapped_column(
        Geometry(
            geometry_type="MULTIPOLYGON",
            srid=4326,
        ),
        nullable=True,
        unique=False,
        comment="Geometry of the forged geographic entity",
    )
    items = relationship(
        "GeoForgedItem",
        back_populates="geo_forged",
        cascade="all, delete-orphan",
    )
    geo_zones: Mapped[list["GeographicZone"]] = relationship(
        "GeographicZone",
        secondary=lambda: Base.metadata.tables[table_key("geo_forged_item")],
        back_populates="geo_forged",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return (
            f"<GeoForged(id={self.id}, code={self.code}, name={self.name}, "
            f"description={self.description}, version={self.version}, "
            f"from_date={self.from_date}, author={self.author}, geometry={self.geometry})>"
        )


class GeoForgedItem(Base):
    """Represents an item of a forged geographic entity in the database.

    :param geo_forged_id: ID of the associated forged geographic entity
    :type geo_forged_id: int
    :param geo_zone_id: ID of the associated geo zone
    :type geo_zone_id: int
    :param rank: Rank of the forged geographic entity item
    :type rank: int
    :param operation: Operation type (ADD, DEL, INTER, EXCL)
    :type operation: str
    :param geo_forged: The associated forged geographic entity
    :type geo_forged: GeoForged
    :param geo_zone: The associated geo zone
    :type geo_zone: GeographicZone

    .. methods::
        - `to_dict()`: Converts the GeoForgedItem object to a dictionary.
        - `from_dict()`: Creates a GeoForgedItem object from a dictionary.
    
    .. table:: `geo_forged_item`

    .. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    __tablename__ = "geo_forged_item"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="ID of the forged geographic entity item",
    )
    geo_forged_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(foreign_key_target("geo_forged")),
        nullable=False,
        unique=False,
        comment="ID of the associated forged geographic entity",
    )
    geo_zone_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(foreign_key_target("geo_zones")),
        nullable=False,
        unique=False,
        comment="ID of the associated geo zone",
    )
    rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=False,
        comment="Rank of the forged geographic entity item",
    )
    operation: Mapped[str] = mapped_column(
        Enum(
            "UNION",
            "DIFFERENCE",
            "INTERSECTION",
            "EXCLUDE",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        unique=False,
        comment="Operation type of the forged geographic entity item",
    )
    geo_forged = relationship(
        "GeoForged",
        back_populates="items",
        foreign_keys=[geo_forged_id],
    )
    geo_zone = relationship(
        "GeographicZone",
        back_populates="geo_forged_items",
        foreign_keys=[geo_zone_id],
    )
