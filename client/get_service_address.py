import json
import os
from urllib.parse import urlparse


def get_service_address(file_path='/tmp/envoy.conf'):
    if 'SERVICE_ADDR' in os.environ:
        service_address = os.getenv('SERVICE_ADDR')
    else:
        envoy_source = json.load(open(file_path))
        url_parse = urlparse(envoy_source['cluster_manager']['clusters'][0]['hosts'][0]['url'])
        service_address = url_parse.netloc
    return service_address
