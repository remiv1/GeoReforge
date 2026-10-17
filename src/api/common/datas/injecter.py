"""Import geographic source files and persist their provenance.

.. classes::
    - `AgregateZone`: Groups shapefile components for a source dataset.
    - `DataInjecter`: Maps source features and stores zones with import manifests.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0
"""
from __future__ import annotations

from io import BytesIO
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator, Any, cast

import shapefile
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from geoalchemy2.elements import WKTElement
from shapely.geometry import MultiPolygon, Polygon, shape as shapely_shape

from .mapper import ZonesMapper
from ..db_objects.file_import import FileImport, file_import_config_key
from ..repositories import GeoZonesRepo
from ..db_objects.geo_zones import GeographicZone as GeoZone
from ...config import DatabaseSettings, DatabaseConfig
from ..other_objects.data_theme import DataTheme

LOGGER = logging.getLogger(__name__)

@dataclass
class AgregateZone:
    """
    Groups the shapefile components for one geographic dataset.

    :param source_name: Basename shared by the shapefile components.
    :type source_name: str
    :param shp: BytesIO object representing the shapefile (.shp).
    :type shp: BytesIO
    :param shx: BytesIO object representing the shape index file (.shx).
    :type shx: BytesIO
    :param dbf: BytesIO object representing the attribute table (.dbf).
    :type dbf: BytesIO
    
    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    source_name: str
    shp: BytesIO
    shx: BytesIO
    dbf: BytesIO

class DataInjecter:
    """
    Import mapped source features and associate them with FileImport manifests.
    
    :param path_list: List of Path objects representing the paths to inject data from.
    :type path_list: list[Path]
    :param data_themes: Dataset configurations corresponding to the downloaded files.
    :type data_themes: list[DataTheme] | None

    .. methods::
        - `__init__`: Initialize the importer and database repository.
        - `_iter_gemetries`: Yield source properties and geometries.
        - `_build_reader`: Create a shapefile reader from its components.
        - `_build_aggregates`: Group compatible shapefile components.
        - `_register_file_import`: Reuse or persist an import manifest.
        - `_mapping_for_aggregate`: Resolve and validate the source mapping.
        - `_inject_aggregate`: Persist features from one dataset.
        - `inject_geo_zones`: Import all configured geographic sources.

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
    """

    def __init__(self, path_list: list[Path], data_themes: list[DataTheme] | None = None):
        """Initialize the source importer and its database repository.

        :param path_list: Paths to downloaded shapefile components.
        :type path_list: list[Path]
        :param data_themes: Dataset configurations associated with the files.
        :type data_themes: list[DataTheme] | None

        :return: None.
        :rtype: None
        """
        ds = DatabaseSettings()
        dc = DatabaseConfig(ds)
        self.path_list: list[Path] = path_list
        self.session = dc.session
        self.repo = GeoZonesRepo()
        self.zones_mapper: ZonesMapper | None = None
        self.data_themes = data_themes or []

    def _iter_gemetries(
        self,
        reader: shapefile.Reader,
    ) -> Iterator[tuple[dict[str, Any], WKTElement]]:
        """Yield source properties and multipolygon geometries from a shapefile reader.

        :param reader: Reader for one source shapefile.
        :type reader: shapefile.Reader
        :return: Iterator of source properties and their geometries.
        :rtype: Iterator[tuple[dict[str, Any], WKTElement]]

        :raises ValueError: If a feature has an unsupported geometry type.
        """
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
                    LOGGER.error(
                        "Unsupported source geometry type: %s",
                        geometry.geom_type,
                    )
                    raise ValueError(f"Unsupported source geometry type: {geometry.geom_type}.")
                yield (
                    shape_rec.record.as_dict(),
                    WKTElement(geometry.wkt, srid=4326),
                )

    def _build_reader(self, geo_zone_file: AgregateZone) -> shapefile.Reader:
        """Build a shapefile reader from its component files.

        :param geo_zone_file: Aggregate containing the shapefile components.
        :type geo_zone_file: AgregateZone
        :return: Reader for the aggregated shapefile.
        :rtype: shapefile.Reader

        :raises shapefile.ShapefileException: If the shapefile components are invalid.
        """
        return shapefile.Reader(
            shp=geo_zone_file.shp,
            shx=geo_zone_file.shx,
            dbf=geo_zone_file.dbf,
        )

    def _build_aggregates(self) -> list[AgregateZone]:
        """Group complete shapefile component sets by basename.

        :return: List of aggregate zone instances.
        :rtype: list[AgregateZone]

        :raises OSError: If a shapefile component cannot be read.
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

    def _register_file_import(self, theme: DataTheme) -> tuple[FileImport, bool]:
        """Reuse or persist a manifest for a normalized dataset configuration.

        :param theme: Dataset configuration to persist.
        :type theme: DataTheme

        :return: The persisted manifest and whether it was newly created.
        :rtype: tuple[FileImport, bool]

        :raises SQLAlchemyError: If the manifest cannot be persisted.
        """
        configuration = {
            "source_path": theme.source_path,
            "data_family": theme.data_family,
            "name": theme.name,
            "precision": theme.precision,
            "link": theme.link,
            "mapping": theme.mapping,
        }
        config_key = file_import_config_key(configuration)
        session = self.repo.session
        existing = session.scalar(
            select(FileImport).where(FileImport.config_key == config_key)
        )
        if existing is not None:
            return existing, False
        file_import = FileImport(config_key=config_key, **configuration)
        session.add(file_import)
        session.flush()
        return file_import, True

    def _mapping_for_aggregate(
        self,
        source_name: str,
        theme: DataTheme | None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Resolve and validate field and class mappings for one dataset.

        :param source_name: Basename of the dataset's shapefile components.
        :type source_name: str
        :param theme: Dataset configuration, or ``None`` for local callers.
        :type theme: DataTheme | None

        :return: Field mapping and class-value mapping.
        :rtype: tuple[dict[str, Any], dict[str, str]]

        :raises ValueError: If a mapping is missing or incomplete.
        """
        if theme is not None:
            fields = theme.mapping
            classes = fields.get("classes", {})
        else:
            mapper = self.zones_mapper
            if mapper is None:
                raise ValueError("The source mapping has not been loaded.")
            mapping_key = next(
                (
                    key for key in mapper.mapping
                    if source_name.endswith(f"_{key}")
                ),
                None,
            )
            if mapping_key is None:
                raise ValueError(f"No mapping was found for {source_name}.")
            fields = mapper.get_mapper(mapping_key)
            classes = mapper.get_classes()
        if not isinstance(classes, dict) or not all(
            isinstance(fields.get(key), str) and fields[key]
            for key in ("class", "code", "name")
        ):
            raise ValueError(f"The mapping for {source_name} is incomplete.")
        return fields, cast(dict[str, str], classes)

    def _inject_aggregate(
        self,
        aggregate: AgregateZone,
        fields: dict[str, Any],
        classes: dict[str, str],
        file_import: FileImport | None,
    ) -> None:
        """Persist all mapped features from one dataset aggregate.

        :param aggregate: Shapefile components to import.
        :type aggregate: AgregateZone
        :param fields: Source attribute names for class, code, and name.
        :type fields: dict[str, Any]
        :param classes: Mapping from source classes to normalized values.
        :type classes: dict[str, str]
        :param file_import: Source manifest, if available.
        :type file_import: FileImport | None

        :return: None.
        :rtype: None

        :raises ValueError: If a feature has no valid source class.
        :raises shapefile.ShapefileException: If the shapefile cannot be read.
        :raises SQLAlchemyError: If a geographic zone cannot be persisted.
        """
        reader = self._build_reader(aggregate)
        try:
            for properties, geometry in self._iter_gemetries(reader):
                source_kind = properties.get(fields["class"])
                if not isinstance(source_kind, str):
                    raise ValueError(
                        f"The source class is missing for {aggregate.source_name}."
                    )
                self.repo.add_geo_zone(
                    GeoZone(
                        kind=classes.get(source_kind, source_kind),
                        code=properties.get(fields["code"]),
                        name=properties.get(fields["name"]),
                        boundary=geometry,
                        file_import=file_import,
                    ),
                    commit=False,
                )
        finally:
            reader.close()

    def inject_geo_zones(self) -> None:
        """Import all configured geographic sources into the database.

        :return: None.
        :rtype: None

        :raises ValueError: If a source file or mapping is invalid.
        :raises OSError: If a shapefile component cannot be read.
        :raises SQLAlchemyError: If source manifests or zones cannot be persisted.
        """
        try:
            themes = getattr(self, "data_themes", [])
            themes_by_stem = {
                Path(theme.url_route).stem: theme for theme in themes
            }
            self.zones_mapper = ZonesMapper() if not themes_by_stem else None
            for aggregate in self._build_aggregates():
                theme = themes_by_stem.get(aggregate.source_name)
                if themes and theme is None:
                    raise ValueError(
                        f"The import configuration is missing for {aggregate.source_name}."
                    )
                file_import = None
                if theme is not None:
                    file_import, is_new = self._register_file_import(theme)
                    if not is_new:
                        continue
                fields, classes = self._mapping_for_aggregate(aggregate.source_name, theme)
                self._inject_aggregate(aggregate, fields, classes, file_import)
        except Exception:
            self.repo.rollback()
            LOGGER.exception("Failed to import initial geographic sources.")
            raise
        if not self.repo.commit():
            raise SQLAlchemyError("Failed to commit initial geographic sources.")
