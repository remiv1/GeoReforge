"""
Module for the `DataInjecter` class responsible for injecting data into the database.

.. class:: `DataInjecter`
    Class responsible for injecting data into the database.
"""

from io import BytesIO
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator, Any, cast
import shapefile
from geoalchemy2.elements import WKTElement
from shapely.geometry import MultiPolygon, Polygon, shape as shapely_shape

from .mapper import ZonesMapper
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
    source_name: str
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
        self.zones_mapper = None

    def _iter_gemetries(
        self,
        reader: shapefile.Reader,
    ) -> Iterator[tuple[dict[str, Any], WKTElement]]:
        """Iterates over geometries in the shapefile reader."""
        for shape_rec in reader.iterShapeRecords():
            if shape_rec.record is not None and shape_rec.shape is not None:
                geo_interface = cast(
                    dict[str, Any],
                    shape_rec.shape.__geo_interface__,
                )
                geometry = shapely_shape(geo_interface)
                if isinstance(geometry, Polygon):
                    geometry = MultiPolygon([geometry])
                elif not isinstance(geometry, MultiPolygon):
                    raise ValueError(
                        f"Type de géométrie non pris en charge : {geometry.geom_type}"
                    )
                yield (
                    shape_rec.record.as_dict(),
                    WKTElement(geometry.wkt, srid=4326),
                )

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
                        source_name=base_name,
                        shp=BytesIO(files[".shp"].read_bytes()),
                        dbf=BytesIO(files[".dbf"].read_bytes()),
                        shx=BytesIO(files[".shx"].read_bytes()),
                    )
                )
        return aggregates

    def inject_geo_zones(self):
        """Injects geo zones into the database."""
        self.zones_mapper = ZonesMapper()
        for gzf in self._build_aggregates():
            mapping_key = next(
                (
                    key for key in self.zones_mapper.mapping
                    if gzf.source_name.endswith(f"_{key}")
                ),
                None,
            )
            if mapping_key is None:
                raise ValueError(f"Aucun mapping trouvé pour {gzf.source_name}")

            fields = self.zones_mapper.get_mapper(mapping_key)
            classes = self.zones_mapper.get_classes()
            for properties, geometry in self._iter_gemetries(self._build_reader(gzf)):
                source_kind = properties.get(fields["class"])
                if not isinstance(source_kind, str):
                    raise ValueError(
                        f"Classe source absente pour le mapping {mapping_key}"
                    )
                geo_zone = GeoZone(
                    kind=classes.get(source_kind, source_kind),
                    code=properties.get(fields["code"]),
                    name=properties.get(fields["name"]),
                    boundary=geometry,
                )
                self.repo.add_geo_zone(geo_zone, commit=False)
        self.repo.commit()
