import os
import socket
import uuid
from time import sleep
from hashlib import sha1

import requests

from service_uuid import get_service_uuid, set_service_uuid

status = True
message = ''

SAAS_DELIVERY_TRANSPORT = os.getenv('SAAS_DELIVERY_TRANSPORT', 'http')
SAAS_DELIVERY_URL = os.getenv('SAAS_DELIVERY_URL', '192.168.122.23')
SAAS_DELIVERY_PORT = os.getenv('SAAS_DELIVERY_PORT', 8080)


def sha(string):
    return sha1(string.encode('utf-8')).hexdigest()


def api(url, timeout):
    return requests.get(f"{SAAS_DELIVERY_TRANSPORT}://{SAAS_DELIVERY_URL}:{SAAS_DELIVERY_PORT}/{url}",
                        timeout=timeout)


def api_wait(url, status_codes=None, timeout=5):
    if status_codes is None:
        status_codes = [200]
    http_fails = 0
    while True:
        try:
            r = api(url, timeout=timeout)
            if r.status_code in status_codes:
                return r
            http_fails = http_fails + 1
            sleep(1)
        except Exception as e:
            http_fails = http_fails + 1
            sleep(1)
        if http_fails % 10 == 0:
            print("SAAS api not realy not healthy")


def check_open_port(address, kill_proxy=True, wait_time=60):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host, port = address.split(':')
    for i in range(int(os.getenv('WAITING_TIME', wait_time))):
        result = sock.connect_ex((host, int(port)))
        # if port is open save file! and start work proxy
        print(f'Ping service port {i} seconds')
        if result == 0:
            with open('/tmp/proxy.file', 'w') as f:
                f.write(address)
                exit(0)
        sleep(1)
    # if port not open, kill proxy
    if kill_proxy:
        print('Service not healthy')
        return False


def find_service(_uuid):
    saas = api_wait(f'find/{_uuid}', status_codes=[200, 501])
    if saas.status_code == 501:
        print(saas.json()['error'])
        sleep(5)
        return find_service(_uuid)
    else:
        print(saas.json()['message'])
        return get_status(_uuid, status_codes=[200])


def get_check(_uuid):
    _sha = sha(_uuid)
    check = api_wait(f'check/{_sha}')
    data = check.json()
    if 'error' in data:
        print(data['error'])
        return find_service(_uuid)
    else:
        # if all is ok start proxy
        check_open_port(data['address'])
        # if not healthy
        cleanup(_uuid)
        return get_status(_uuid)


def cleanup(_sha):
    print("Run cleanup and wait 15 seconds")
    sleep(5)
    api_wait(f'cleanup/{_sha}')
    sleep(10)


def get_status(_uuid, status_codes=None):
    if status_codes is None:
        status_codes = [200, 400]
    global message
    _sha = sha(_uuid)
    status = api_wait(f'status/{_sha}', status_codes=status_codes)
    if status.status_code == 400:
        print(status.json()['error'])
        return get_check(_uuid)
    else:
        data = status.json()
        if 'error' in data:
            print(data['error'])
            cleanup(_uuid)
            return get_status(_uuid)
        this_message = status.json()['message']
        if message != this_message:
            message = this_message
            print(message)
        if 'address' not in data:
            sleep(0.5)
            return get_status(_uuid)
        # if all is ok start proxy
        check_open_port(data['address'])
        # if not healthy
        cleanup(_uuid)
        return get_status(_uuid)


# set uuid
INHERITED_SERVICE_UUID = os.getenv("INHERITED_SERVICE_UUID", "")
if INHERITED_SERVICE_UUID == "":
    if os.path.isfile('/tmp/uuid.file'):
        INHERITED_SERVICE_UUID = get_service_uuid()
    else:
        INHERITED_SERVICE_UUID = str(uuid.uuid4())
print(f"Use {INHERITED_SERVICE_UUID} uuid")
set_service_uuid(INHERITED_SERVICE_UUID)

# check local save file and ping service if exist
with open('/tmp/local.file', 'w') as local:
    PROXY_ADDR = os.getenv("PROXY_ADDR", "0.0.0.0:80")
    if PROXY_ADDR.startswith("tcp://"):
        PROXY_ADDR = PROXY_ADDR[len("tcp://"):]
    local.write(PROXY_ADDR)

print("Check you client version")
server_version = api_wait('version').text
client_version = '2'
if server_version != client_version:
    print(f"""
    You client version is {client_version} SAAS service is {server_version}
    Please pull new client version
    """)
    exit(1)
print("Client version is valid")

print(f'Get status for {INHERITED_SERVICE_UUID} ===> {sha(INHERITED_SERVICE_UUID)}')
# infinity delivery dir
get_status(INHERITED_SERVICE_UUID)
