import os
from time import sleep

from socketIO_client import SocketIO, BaseNamespace

from get_service_address import get_service_address


class ChatNamespace(BaseNamespace):

    def on_ping(self, address):
        sleep(10)
        chat_namespace.emit('ping', address)

    def on_ping_tmp(self, address):
        sleep(10)
        chat_namespace.emit('ping tmp', address)


while True:
    try:
        socketIO = SocketIO(os.getenv('SAAS_DELIVERY_URL', '10.100.31.41'), int(os.getenv('SAAS_DELIVERY_PORT', 8080)))
        chat_namespace = socketIO.define(ChatNamespace, '/saas')

        if 'PING_TMP' in os.environ:
            chat_namespace.emit('ping tmp', get_service_address())
        else:
            chat_namespace.emit('ping', get_service_address())
        socketIO.wait(seconds=60)
        print("reconnect ping service")
    except Exception as e:
        print(e)
