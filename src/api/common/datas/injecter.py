"""
Module for the `DataInjecter` class responsible for injecting data into the database.

.. class:: `DataInjecter`
    Class responsible for injecting data into the database.
"""

import json
from io import BytesIO
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator, Any
import shapefile

from ..repositories import GeoZonesRepo
from ..db_objects.geo_zones import GeographicZone as GeoZone
from ...config import DatabaseSettings, DatabaseConfig

LOGGER = logging.getLogger(__name__)

@dataclass
class AgregateZone:
    """
    Represents an aggregate zone with its associated shapefile, geometry, and attribute table.

    :param shp: BytesIO object representing the shapefile (.shp).
    :param shx: BytesIO object representing the shape index file (.shx).
    :param dbf: BytesIO object representing the attribute table (.dbf).
    """
    shp: BytesIO
    shx: BytesIO
    dbf: BytesIO

class DataInjecter:
    """
    Class responsible for injecting data into the database.
    
    :param path_list: List of Path objects representing the paths to inject data from.
    :type path_list: list[Path]

    .. author:: Remi Verschuur <remi.verschuur@example.com>
    .. version:: 1.0
    """

    def __init__(self, path_list: list[Path]):
        """Initializes the DataInjecter instance."""
        ds = DatabaseSettings()
        dc = DatabaseConfig(ds)
        self.path_list = path_list
        self.session = dc.session
        self.repo = GeoZonesRepo()

    def _iter_gemetries(self, reader: shapefile.Reader) -> Iterator[tuple[dict[str, Any], str]]:
        """Iterates over geometries in the shapefile reader."""
        for shape_rec in reader.iterShapeRecords():
            if shape_rec.record is not None and shape_rec.shape is not None:
                yield shape_rec.record.as_dict(), json.dumps(shape_rec.shape.__geo_interface__)

    def _build_reader(self, geo_zone_file: AgregateZone) -> shapefile.Reader:
        """Builds a shapefile reader from the given aggregate zone file."""
        return shapefile.Reader(
            shp=geo_zone_file.shp,
            shx=geo_zone_file.shx,
            dbf=geo_zone_file.dbf,
        )

    def _build_aggregates(self) -> list[AgregateZone]:
        """Builds aggregate zones from the given list of paths, considering names:
        
        - group files by name for each extention
        - match files with the same base name to form an aggregate zone
        - create AgregateZone instances for each matched set of files
        """
        aggregates: list[AgregateZone] = []
        grouped_files: dict[str, dict[str, Path]] = {}
        for path in self.path_list:
            base_name = path.stem
            ext = path.suffix.lower()
            if base_name not in grouped_files:
                grouped_files[base_name] = {}
            grouped_files[base_name][ext] = path

        for base_name, files in grouped_files.items():
            if ".shp" in files and ".shx" in files and ".dbf" in files:
                aggregates.append(
                    AgregateZone(
                        shp=BytesIO(files[".shp"].read_bytes()),
                        dbf=BytesIO(files[".dbf"].read_bytes()),
                        shx=BytesIO(files[".shx"].read_bytes()),
                    )
                )
        return aggregates

    def inject_geo_zones(self, geo_zones_files: list[AgregateZone]):
        """Injects geo zones into the database."""
        for gzf in geo_zones_files:
            for properties, geometry in self._iter_gemetries(self._build_reader(gzf)):
                geo_zone = GeoZone(
                    kind=properties.get("kind"),
                    code=properties.get("ISO_A3"),
                    name=properties.get("NAME_LONG"),
                    boundary=geometry,
                )
                self.repo.add_geo_zone(geo_zone, commit=False)
        self.repo.commit()
