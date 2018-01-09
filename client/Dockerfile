FROM golang:alpine
RUN apk add --update python3 supervisor
RUN apk add --no-cache --virtual .build-deps py3-pip git  \
        && go get github.com/jpillora/go-tcp-proxy/cmd/tcp-proxy \
        && pip3 --no-cache install socketIO-client  \
	&& apk del .build-deps \
	&& rm -rf /var/cache/apk/*
WORKDIR /src
ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "--nodaemon", "--configuration", "/src/supervisord.conf"]
ADD entrypoint.sh /
RUN chmod +x /entrypoint.sh
ADD supervisord.conf *.py ./