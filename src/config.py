"""Configuration file for the Gunicorn server.

:param bind: The address and port to bind the server to.
:type bind: str
:param worker_class: The type of workers to use.
:type worker_class: str
:param workers: The number of worker processes.
:type workers: int
:param threads: The number of threads per worker.
:type threads: int
:param timeout: The worker timeout in seconds.
:type timeout: int
:param keepalive: The keep-alive duration in seconds.
:type keepalive: int
:param loglevel: The logging level.
:type loglevel: str
:param accesslog: The access log file path.
:type accesslog: str
:param errorlog: The error log file path.
:type errorlog: str
:param graceful_timeout: The graceful timeout in seconds.
:type graceful_timeout: int
:param reload: Whether to enable automatic reloading.
:type reload: bool

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""
bind: str = "0.0.0.0:8000"   # pylint: disable=C0103
worker_class: str = "gthread"   # pylint: disable=C0103
workers: int = 2   # pylint: disable=C0103
threads: int = 4   # pylint: disable=C0103
timeout: int = 60   # pylint: disable=C0103
keepalive: int = 5   # pylint: disable=C0103
loglevel: str = "info"   # pylint: disable=C0103
accesslog: str = "-"   # pylint: disable=C0103
errorlog: str = "-"   # pylint: disable=C0103
graceful_timeout: int = 30   # pylint: disable=C0103
reload: bool = False   # pylint: disable=C0103
