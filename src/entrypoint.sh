#!/bin/sh

# Entry point script for the GeoReforge application.
# .. Author:: Rémi Verschuur <rverschuur@audit-io.fr>
# .. version:: 1.0.0

set -e
python -m api.bootstrap
exec gunicorn -c /etc/app/config.py api.main:app