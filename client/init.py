import os
import socket
import uuid
from time import sleep

import requests

from get_service_address import get_service_address
from service_uuid import get_service_uuid, set_service_uuid

delivery = True

SAAS_DELIVERY_TRANSPORT = os.getenv('SAAS_DELIVERY_TRANSPORT', 'http')
SAAS_DELIVERY_URL = os.getenv('SAAS_DELIVERY_URL', '10.100.31.41')
SAAS_DELIVERY_PORT = os.getenv('SAAS_DELIVERY_PORT', 8080)


def api(url):
    try:
        r = requests.get(f"{SAAS_DELIVERY_TRANSPORT}://{SAAS_DELIVERY_URL}:{SAAS_DELIVERY_PORT}/{url}", timeout=20)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(e)
        sleep(5)
    return []


def delivery_dir(my_uuid=None, retry=0):
    if my_uuid is None:
        my_uuid = get_service_uuid()
    if retry > 30:
        print(f'{my_uuid} delivery: did not wait for service, retry')
        return False
    data = api(f'delivery/{my_uuid}')
    if 'directory' not in data:
        return delivery_dir(my_uuid, retry + 1)
    elif data['directory'] is None:
        print(f'Directory for {my_uuid} not ready, please wait')
        sleep(2)
        return delivery_dir(my_uuid, retry + 1)
    else:
        print(f'Waiting directory for {my_uuid}')
        return waiting_dir(my_uuid)


def waiting_dir(my_uuid=None, retry=0):
    if my_uuid is None:
        my_uuid = get_service_uuid()
    if retry > 120:
        print(f'{my_uuid} waiting: did not wait for service, retry')
        return False
    data = api(f'waiting/{my_uuid}')
    if 'address' not in data:
        return waiting_dir(my_uuid, retry + 1)
    elif data['address'] == "---":
        # if can't create dir, let's restart
        print(f"Can't create dir for {my_uuid}, let's restart")
        sleep(2)
        return delivery_dir(get_service_uuid())
    elif data['address'] is not None:
        print(f"Service address {data['address']}")
        if check_open_port(data['address']):
            with open('/tmp/proxy.file', 'w') as f:
                f.write(data['address'])
            exit(0)
        return False
    else:
        print(f'Waiting container for {my_uuid}')
        sleep(2)
        return waiting_dir(my_uuid, retry + 1)


def health_check(address):
    data = api(f'health_check/{address}')
    if 'uuid' not in data:
        health_check(address)
    elif data['uuid'] is not None:
        if check_open_port(get_service_address(), kill_proxy=False, wait_time=1):
            exit(0)
    print(f"You old service {address} not found")


def check_open_port(address, kill_proxy=True, wait_time=60):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host, port = address.split(':')
    for i in range(int(os.getenv('WAITING_TIME', wait_time))):
        result = sock.connect_ex((host, int(port)))
        # if port is open save file! and start work proxy
        print(f'Ping service port {i} seconds')
        if result == 0:
            return True
        sleep(1)
    # if port not open, kill proxy
    if kill_proxy:
        print('Service not healthy')
        return False


print('Run connector')

# set uuid
INHERITED_SERVICE_UUID = os.getenv("INHERITED_SERVICE_UUID", "")
if INHERITED_SERVICE_UUID != "":
    print("Try use inherited service uuid")
    set_service_uuid(os.getenv('INHERITED_SERVICE_UUID'))
    data = api(f"health_check_uuid/{os.getenv('INHERITED_SERVICE_UUID')}")
    if 'address' in data and data['address'] is not None:
        with open('/tmp/proxy.file', 'w') as f:
            f.write(data['address'])
else:
    set_service_uuid(str(uuid.uuid4()))

# set addr
INHERITED_SERVICE_ADDR = os.getenv("INHERITED_SERVICE_ADDR", "")
if INHERITED_SERVICE_ADDR != "":
    print("Try use inherited service address")
    with open('/tmp/proxy.file', 'w') as f:
        f.write(os.getenv('INHERITED_SERVICE_ADDR'))

# check local save file and ping service if exist
with open('/tmp/local.file', 'w') as local:
    PROXY_ADDR = os.getenv("PROXY_ADDR", "0.0.0.0:80")
    if PROXY_ADDR.startswith("tcp://"):
        PROXY_ADDR = PROXY_ADDR[len("tcp://"):]
    local.write(PROXY_ADDR)

if os.path.isfile('/tmp/proxy.file'):
    print("Found proxy config, try connect to service")
    health_check(get_service_address())

print("Start delivery")
# infinity delivery dir
while delivery:
    delivery = delivery_dir(get_service_uuid())
    if not delivery:
        # retry with new uuid
        sleep(5)
        delivery = True
