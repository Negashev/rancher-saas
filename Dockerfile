FROM alpine

WORKDIR /src

ENV DATA_DIR=/data

VOLUME /source

RUN apk add --update python3
RUN apk add --update zfs
RUN apk add --no-cache --virtual .build-deps build-base python3-dev libffi-dev openssl-dev py3-pip \
    && pip3 --no-cache install apscheduler aiodocker requests asyncio-nats-client \
           weir https://github.com/squeaky-pl/japronto/archive/master.zip \
	&& apk del .build-deps \
	&& rm -rf /var/cache/apk/*

ADD *.py ./
