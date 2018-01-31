FROM alpine

WORKDIR /src

ENV DATA_DIR=/data

VOLUME /data
VOLUME /source

RUN apk add --update python3
RUN apk add --update --virtual .build-deps build-base py3-pip python3-dev && \
	pip3 --no-cache install ignite elasticsearch aiohttp apscheduler asyncio-nats-client aiodocker python-socketio \
	https://github.com/cr0hn/aiotasks/archive/master.zip && \
	apk del .build-deps && \
	rm -rf /var/cache/apk/*

ADD store ./store
ADD *.py ./
