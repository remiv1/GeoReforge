"""
Module for common repository functionalities.

.. author:: Remi Verschuur <remi.verschuur@example.com>
.. version:: 1.0
"""

import logging

from sqlalchemy.exc import SQLAlchemyError

from ...config import DatabaseSettings, DatabaseConfig

logger = logging.getLogger(__name__)

class CommonRepo:
    """
    Class responsible for common repository functionalities.

    .. method:: `commit()`
        Commits the current transaction to the database.

    .. method:: `rollback()`
        Rolls back the current transaction in the database.

    .. author:: Remi Verschuur <rverschuur@audit-io.fr>
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
            logger.exception("Commit failed, transaction rolled back.", exc_info=e)
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
            logger.exception("Rollback failed.", exc_info=e)
            return False
