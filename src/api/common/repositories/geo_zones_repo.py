"""
Module for the `GeoZonesRepo` class responsible for managing geographical zones in the database.

.. classes::
    - `GeoZonesRepo`: Class responsible for managing geographical zones in the database.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

import logging
from sqlalchemy import select

from .common import CommonRepo
from ..db_objects.geo_zones import GeographicZone as GeoZone

class GeoZonesRepo(CommonRepo):
    """
    Class responsible for managing geographical zones in the database.

    .. methods::
        - `get_geo_zone(geo_zone_id: int)`: Retrieves a geo zone by its ID.
        - `get_all_geo_zones()`: Retrieves all geo zones.
        - `add_geo_zone(geo_zone: GeoZone, commit: bool = True)`: Adds a new geo zone
        to the database.
        - `delete_geo_zone(geo_zone: GeoZone, commit: bool = True)`: Deletes a geo zone
        from the database.
        - `update_geo_zone(geo_zone: GeoZone, commit: bool = True)`: Updates an existing
        geo zone in the database.

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
    """

    def __init__(self):
        """Initializes the GeoZonesRepo instance.
        
        :return: None
        :rtype: None

        .. notes::
            New init permits setting up the logger for the repository instance.
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def get_geo_zone(self, geo_zone_id: int):
        """Retrieves a geo zone by its ID.
        
        :param geo_zone_id: The ID of the geo zone to retrieve.
        :type geo_zone_id: int
        :return: The geo zone with the specified ID, or None if not found.
        :rtype: GeoZone or None
        """
        stmt = select(GeoZone).where(GeoZone.id == geo_zone_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_all_geo_zones(self):
        """Retrieves all geo zones.
        
        :return: A list of all geo zones.
        :rtype: list[GeoZone]
        """
        stmt = select(GeoZone)
        return self.session.execute(stmt).scalars().all()

    def add_geo_zone(self, geo_zone: GeoZone, commit: bool = True):
        """Adds a new geo zone to the database.
        
        :param geo_zone: The geo zone to add.
        :type geo_zone: GeoZone
        :param commit: Whether to commit the transaction immediately.
        :type commit: bool
        :return: The added geo zone.
        :rtype: GeoZone

        .. note:: Default value for the `commit` parameter is `True`.
        """
        self.session.add(geo_zone)
        if commit:
            self.commit()
        return geo_zone

    def delete_geo_zone(self, geo_zone: GeoZone, commit: bool = True):
        """Deletes a geo zone from the database.
        
        :param geo_zone: The geo zone to delete.
        :type geo_zone: GeoZone
        :param commit: Whether to commit the transaction immediately.
        :type commit: bool
        :return: The deleted geo zone.
        :rtype: GeoZone

        .. note:: Default value for the `commit` parameter is `True`.
        """
        self.session.delete(geo_zone)
        if commit:
            self.commit()
        return geo_zone

    def update_geo_zone(self, geo_zone: GeoZone, commit: bool = True):
        """Updates an existing geo zone in the database.
        
        :param geo_zone: The geo zone to update.
        :type geo_zone: GeoZone
        :param commit: Whether to commit the transaction immediately.
        :type commit: bool
        :return: The updated geo zone.
        :rtype: GeoZone

        .. note:: Default value for the `commit` parameter is `True`.
        """
        self.session.add(geo_zone)
        if commit:
            self.commit()
        return geo_zone
