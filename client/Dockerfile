FROM golang:alpine as proxy_compilate
RUN apk add --update git
RUN go get github.com/jpillora/go-tcp-proxy/cmd/tcp-proxy

FROM alpine
EXPOSE 8080
RUN apk add --update python3
RUN apk add --update supervisor
RUN apk add --update py3-requests

ADD requirements.txt ./

RUN apk add --no-cache --virtual .build-deps py3-pip build-base python3-dev \
    && pip3 --no-cache install -r requirements.txt \
	&& apk del .build-deps \
	&& rm -rf /var/cache/apk/*
WORKDIR /src
ENTRYPOINT ["/entrypoint.sh"]
CMD ["--prefix", ""]
ADD entrypoint.sh /
RUN chmod +x /entrypoint.sh
COPY --from=proxy_compilate /go/bin/tcp-proxy /bin/tcp-proxy
ADD supervisord.conf *.py ./
