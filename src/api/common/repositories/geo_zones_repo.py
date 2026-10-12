"""
Module for the `GeoZonesRepo` class responsible for managing geo zones in the database.

.. class:: `GeoZonesRepo`
    Class responsible for managing geo zones in the database.
"""

from sqlalchemy import select

from .common import CommonRepo
from ..db_objects.geo_zones import GeographicZone as GeoZone

class GeoZonesRepo(CommonRepo):
    """
    Class responsible for managing geo zones in the database.

    .. author:: Remi Verschuur <remi.verschuur@example.com>
    .. version:: 1.0
    """

    def get_geo_zone(self, geo_zone_id: int):
        """Retrieves a geo zone by its ID."""
        stmt = select(GeoZone).where(GeoZone.id == geo_zone_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_all_geo_zones(self):
        """Retrieves all geo zones."""
        stmt = select(GeoZone)
        return self.session.execute(stmt).scalars().all()

    def add_geo_zone(self, geo_zone: GeoZone, commit: bool = True):
        """Adds a new geo zone to the database."""
        self.session.add(geo_zone)
        if commit:
            self.session.commit()
        return geo_zone

    def delete_geo_zone(self, geo_zone: GeoZone, commit: bool = True):
        """Deletes a geo zone from the database."""
        self.session.delete(geo_zone)
        if commit:
            self.session.commit()
        return geo_zone

    def update_geo_zone(self, geo_zone: GeoZone, commit: bool = True):
        """Updates an existing geo zone in the database."""
        self.session.add(geo_zone)
        if commit:
            self.session.commit()
        return geo_zone
