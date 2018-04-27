FROM golang:alpine as proxy_compilate
RUN apk add --update git
RUN go get github.com/jpillora/go-tcp-proxy/cmd/tcp-proxy

FROM alpine
EXPOSE 8080
RUN apk add --update python3
RUN apk add --update supervisor
RUN apk add --no-cache --virtual .build-deps py3-pip build-base python3-dev \
    && pip3 --no-cache install apscheduler requests \
    https://github.com/squeaky-pl/japronto/archive/master.zip  \
	&& apk del .build-deps \
	&& rm -rf /var/cache/apk/*
WORKDIR /src
ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "--nodaemon", "--configuration", "/src/supervisord.conf"]
ADD entrypoint.sh /
RUN chmod +x /entrypoint.sh
COPY --from=proxy_compilate /go/bin/tcp-proxy /bin/tcp-proxy
ADD supervisord.conf *.py ./