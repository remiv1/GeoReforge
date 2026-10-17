"""Data structures describing configured geographic data themes.

.. classes::
    - `DataTheme`: Immutable download and mapping configuration for one dataset resolution.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class DataTheme:
    """Immutable download and mapping configuration for one dataset resolution.

    :param name: Human-readable dataset name.
    :type name: str
    :param data_family: Source data family, such as cultural or physical.
    :type data_family: str
    :param precision: Resolution configured in zones.toml.
    :type precision: str
    :param link: Natural Earth dataset URL suffix.
    :type link: str
    :param source_path: Base URL of the source provider.
    :type source_path: str
    :param mapping: Source column and class mappings.
    :type mapping: dict[str, Any]
    :param url_route: Fully qualified download URL.
    :type url_route: str

    .. methods::
        - `__init__`: Initialize an immutable dataset configuration.

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0.0
    """
    name: str
    data_family: str
    precision: str
    link: str
    source_path: str
    mapping: dict[str, Any]
    url_route: str
