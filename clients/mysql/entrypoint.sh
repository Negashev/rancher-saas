#! /bin/sh
set -e
# init or reinit
python3 /src/init.py
exec "$@"