"""Database object for geo zones."""

from sqlalchemy import String
from sqlalchemy.orm import mapped_column, Mapped
from geoalchemy2 import Geometry

from . import Base, TABLE_ARGS

class GeographicZone(Base):  # pylint: disable=R0903
    """Database object for geo zones."""
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
        unique=True,
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
