import os
import json
import socket
from time import sleep

from socketIO_client import SocketIO, BaseNamespace

from get_service_address import get_service_address

delivery = True


def check_open_port(address):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host, port = address.split(':')
    for i in range(int(os.getenv('WAITING_TIME', 30))):
        result = sock.connect_ex((host, int(port)))
        # if port is open save file! and start work proxy
        print(f'Ping service port {i} seconds')
        if result == 0:
            return
        sleep(1)
    # if port not open, kill service
    exit('Service not healthy')


class ChatNamespace(BaseNamespace):

    def on_health_check(self, uuid):
        global delivery
        if uuid:
            exit(0)
        else:
            delivery = False
            print("You old service not found")
            chat_namespace.emit('get uuid')

    def on_set_uuid(self, uuid):
        global delivery
        delivery = False
        print('Delivery directory')
        self.emit('delivery', {'uuid': uuid})

    def on_delivery(self, data):
        if data['directory'] is None:
            print('You directory not ready, please wait')
            sleep(2)
            self.emit('delivery', data)
        else:
            print('Waiting directory')
            # if you don't trust for redis :)
            self.emit('waiting', {'uuid': data['uuid']})

    def on_waiting(self, data):
        if data['address'] is None:
            print('you directory not ready, please wait')
            sleep(2)
            self.emit('waiting', data)
        else:
            print(f"Service address {data['address']}")
            check_open_port(data['address'])
            with open('/tmp/proxy.file', 'w') as f:
                f.write(data['address'])
            exit(0)


# check local save file and ping service if exist
with open('/tmp/local.file', 'w') as local:
    PROXY_ADDR = os.getenv("PROXY_ADDR", "0.0.0.0:80")
    if PROXY_ADDR.startswith("tcp://"):
        PROXY_ADDR = PROXY_ADDR[len("tcp://"):]
    local.write(PROXY_ADDR)

while delivery:
    print("Connecting to delivery service")
    socketIO = SocketIO(os.getenv('SAAS_DELIVERY_URL', '10.100.31.41'), int(os.getenv('SAAS_DELIVERY_PORT', 8080)))
    chat_namespace = socketIO.define(ChatNamespace, '/saas')
    print("Success connect")
    if os.path.isfile('/tmp/proxy.file'):
        print("Found proxy config, try connect to service")
        chat_namespace.emit('health check', get_service_address())
    else:
        print("Start delivery")
        chat_namespace.emit('get uuid')
    if delivery:
        socketIO.wait(300)
        print('Did not wait for service, retry')
        sleep(5)
        delivery = True
    else:
        socketIO.wait()
