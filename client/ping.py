import os
from time import sleep

from socketIO_client import SocketIO, BaseNamespace

from get_service_address import get_service_address


class ChatNamespace(BaseNamespace):

    def on_ping(self, address):
        sleep(10)
        chat_namespace.emit('ping', address)


socketIO = SocketIO(os.getenv('SAAS_DELIVERY_URL', '10.100.31.41'), int(os.getenv('SAAS_DELIVERY_PORT', 8080)))
chat_namespace = socketIO.define(ChatNamespace, '/saas')

chat_namespace.emit('ping', get_service_address())
socketIO.wait()
