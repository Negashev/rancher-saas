FROM alpine

WORKDIR /src

ENV DATA_DIR=/data \
    SOURCE_DIR=/source

VOLUME /data
VOLUME /source

RUN apk add --update python3
RUN apk add --update --virtual .build-deps build-base py3-pip python3-dev git && \
	pip3 --no-cache install ignite aiohttp apscheduler redis aiodocker python-socketio https://github.com/cr0hn/aiotasks/archive/master.zip && \
	apk del .build-deps && \
	rm -rf /var/cache/apk/*

ADD worker ./worker
ADD *.py ./