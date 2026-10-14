"""
Module defining the DataFamily enumeration.

.. classes::
    - `DataFamily` enumeration for data families.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

from enum import Enum

class DataFamily(Enum):
    """
    Enumeration of possible data families.
    
    .. CULTURAL:: Cultural data.
        - type: str
        - value: "cultural"

    .. PHYSICAL:: Physical data.
        - type: str
        - value: "physical"

    .. RASTER:: Raster data.
        - type: str
        - value: "raster"
    
    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    CULTURAL = "cultural"
    PHYSICAL = "physical"
    RASTER = "raster"
