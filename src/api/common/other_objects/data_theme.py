"""
Module defining the DataTheme data structure.

.. classes::
    - `DataTheme` data structure.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class DataTheme:
    """
    Data structure representing a data theme.
    
    :param name: The name of the data theme.
    :type name: str
    :param precisions: The precision level of the data theme.
    :type precisions: int
    :param url_route: The URL route associated with the data theme.
    :type url_route: str

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
    """
    name: str
    precisions: int
    url_route: str
