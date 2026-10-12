"""
Module defining the Precision enumeration for vector data.

.. class:: `Precision` enumeration for vector data.

.. constant:: `PRECISION_MAP` Dictionary mapping string keys to `Precision` enum values.
"""

from enum import Enum

class Precision(Enum):
    """
    Enumeration of possible precision levels for vector data.
    
    .. attribute:: LOW
        Low precision level, value is 110.

    .. attribute:: MEDIUM
        Medium precision level, value is 50.

    .. attribute:: HIGH
        High precision level, value is 10.
    """
    LOW = 110
    MEDIUM = 50
    HIGH = 10

PRECISION_MAP = {
    "low": Precision.LOW,
    "medium": Precision.MEDIUM,
    "high": Precision.HIGH,
}
