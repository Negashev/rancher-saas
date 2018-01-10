import json
import os
from urllib.parse import urlparse


def get_service_address(file_path='/tmp/proxy.file'):
    if 'SERVICE_ADDR' in os.environ:
        service_address = os.getenv('SERVICE_ADDR')
    else:
        f = open(file_path, 'r')
        service_address = f.read()
    return service_address
