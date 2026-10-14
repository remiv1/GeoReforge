"""
Module for common repository functionalities.

.. classes::
    - `CommonRepo` class for common repository functionalities.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError

from ...config import DatabaseSettings, DatabaseConfig

class CommonRepo:
    """
    Class responsible for common repository functionalities.

    .. methods::
        - `commit()`: Commits the current transaction to the database.
        - `rollback()`: Rolls back the current transaction in the database.

    .. author:: Rémi Verschuur <rverschuur@audit-io.fr>
    .. version:: 1.0
    """
    def __init__(self):
        """Initializes the CommonRepo instance.
        
        :return: None
        :rtype: None
        """
        ds = DatabaseSettings()
        dc = DatabaseConfig(ds)
        self.session = dc.session
        self.engine = dc.engine
        self.logger = logging.getLogger(__name__)

    def commit(self) -> bool:
        """Commits the current transaction to the database.
        
        :return: True if the commit was successful
        :rtype: bool
        """
        try:
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            self.logger.exception("Commit failed, transaction rolled back.", exc_info=e)
            return False

    def rollback(self) -> bool:
        """Rolls back the current transaction in the database.
        
        :return: True if the rollback was successful
        :rtype: bool
        """
        try:
            self.session.rollback()
            return True
        except SQLAlchemyError as e:
            self.logger.exception("Rollback failed.", exc_info=e)
            return False
