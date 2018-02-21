FROM pypy:3-slim

WORKDIR /src

ENV DATA_DIR=/data

VOLUME /data
VOLUME /source

RUN pip3 --no-cache install elasticsearch aiohttp apscheduler aiodocker python-socketio requests

ADD store ./store
ADD *.py ./
