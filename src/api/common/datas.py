"""
Common data structures and utilities for the API.
"""
from __future__ import annotations

from enum import Enum
from dataclasses import dataclass

class DataFamily(Enum):
    """Enumeration of possible data families."""
    CULTURAL = "cultural"
    PHYSICAL = "physical"
    RASTER = "raster"

class Precision(Enum):
    """Enumeration of possible precision levels for vector data."""
    LOW = 110
    MEDIUM = 50
    HIGH = 10

@dataclass(frozen=True)
class DataTheme:
    """Data structure representing a data theme."""
    name: str
    precisions: Precision

class DataImporter:
    """Class responsible for importing data themes.
    
    args:
        sources (list[DataTheme]): List of data themes to be imported.
    
    eg:
        countries = DataTheme(
            name="Countries",
            precisions=Precision.HIGH
        )
        disputed_areas = DataTheme(
            name="Disputed Areas",
            precisions=Precision.HIGH
        )
        importer = DataImporter(sources=[countries, disputed_areas])
    """
    def __init__(self, sources: list[DataTheme]):
        self.sources = sources
