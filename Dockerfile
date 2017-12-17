FROM python:alpine

WORKDIR /src

VOLUME /data/source /data/blanks /data/mounted

ENV DATA_DIR=/data \
    BLANKS=10 \
    RANCHER_CLI_VERSION=v0.6.4 \
    COMPOSE_PROJECT_NAME=Default

RUN pip --no-cache install flask Flask-APScheduler requests

ADD https://github.com/rancher/cli/releases/download/$RANCHER_CLI_VERSION/rancher-linux-amd64-$RANCHER_CLI_VERSION.tar.gz /tmp/rancher.tar.gz
RUN tar -xf /tmp/rancher.tar.gz -C /tmp && \
    mv /tmp/rancher-$RANCHER_CLI_VERSION/rancher /usr/bin/

ADD *.py ./
ADD compose ./

CMD ["python", "server.py"]