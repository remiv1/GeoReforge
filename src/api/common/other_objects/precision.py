"""
Module defining the Precision enumeration for vector data.

.. classes::
    - `Precision` enumeration for vector data.

.. constant::
    - `PRECISION_MAP` Dictionary mapping string keys to `Precision` enum values.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

from enum import Enum

class Precision(Enum):
    """
    Enumeration of possible precision levels for vector data.
    
    .. LOW:: Low precision level.
        - type: int
        - value: 110

    .. MEDIUM:: Medium precision level.
        - type: int
        - value: 50

    .. HIGH:: High precision level.
        - type: int
        - value: 10
    
    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    LOW = 110
    MEDIUM = 50
    HIGH = 10

PRECISION_MAP = {
    "low": Precision.LOW,
    "medium": Precision.MEDIUM,
    "high": Precision.HIGH,
}
