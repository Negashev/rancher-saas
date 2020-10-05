FROM alpine

WORKDIR /src

VOLUME /source

RUN apk add --update python3
RUN apk add --update zfs
RUN apk add --update py3-requests

ADD requirements.txt ./

RUN apk add --no-cache --virtual .build-deps build-base python3-dev libffi-dev openssl-dev py3-pip \
    && pip3 --no-cache install -r requirements.txt \
	&& apk del .build-deps \
	&& rm -rf /var/cache/apk/*

ADD *.py ./
