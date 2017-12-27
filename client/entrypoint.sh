#! /bin/sh
set -e
# init or reinit
echo init
python3 /src/init.py
exec "$@"