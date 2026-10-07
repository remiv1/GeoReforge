#!/bin/sh
set -e
python -m api.bootstrap
exec gunicorn -c /etc/app/config.py api.main:app