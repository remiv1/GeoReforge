"""
Module defining the DataFamily enumeration.

.. class:: `DataFamily` enumeration for data families.
"""

from enum import Enum

class DataFamily(Enum):
    """
    Enumeration of possible data families.
    
    .. attribute:: CULTURAL
        Represents cultural data. Value is "cultural".

    .. attribute:: PHYSICAL
        Represents physical data. Value is "physical".

    .. attribute:: RASTER
        Represents raster data. Value is "raster".
    
    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    CULTURAL = "cultural"
    PHYSICAL = "physical"
    RASTER = "raster"
