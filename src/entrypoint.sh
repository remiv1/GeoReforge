#!/bin/sh
set -a
. /etc/app/env.conf
set +a

# Next step to implement: start the application
exec gunicorn -c /etc/app/config.yaml main:app