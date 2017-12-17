import os
import json
import requests
import copy

_GET = 'get'
_POST = 'post'
_PUT = 'put'

V1 = 'v1'
V2_BETA = 'v2-beta'

_HTTP = {
    _GET: requests.get,
    _POST: requests.post,
    _PUT: requests.put
}

_HEADERS = {'Content-Type': 'application/json', 'Accept': 'application/json'}


def _send_request(method, url, json_data=None):
    """Send HTTP request"""
    return _HTTP[method]('{}/{}'.format(os.getenv('RANCHER_URL'), url),
                         auth=(os.getenv('RANCHER_ACCESS_KEY'), os.getenv('RANCHER_SECRET_KEY')),
                         headers=_HEADERS, json=json_data, verify=False)


def get(url):
    """Sends get request"""
    return _send_request(_GET, url)


def post(url, payload):
    """Sends post request"""
    return _send_request(_POST, url, payload)


def put(url, payload):
    """Sends put request"""
    return _send_request(_PUT, url, payload)


def __get_lb_service(service_id):
    end_point = '{}/loadbalancerservices/{}'.format(
        V2_BETA, service_id)
    response = get(end_point)
    if response.status_code not in range(200, 300):
        print('Not get lb config:', response.text)
        exit(2)
    return json.loads(response.text)


def merge(left, right, path=None):
    """Merge dicts"""

    if path is None:
        path = []
    for key in right:
        if key in left:
            if isinstance(left[key], dict) and isinstance(right[key], dict):
                merge(left[key], right[key], path + [str(key)])
            elif left[key] == right[key]:
                pass  # same leaf value
            elif isinstance(left[key], list) and isinstance(right[key], list):
                for item in right[key]:
                    if item not in left[key]:
                        left[key].append(item)
            else:
                raise Exception('Conflict at %s' %
                                '.'.join(path + [str(key)]))
        else:
            left[key] = right[key]
    return left


def update_load_balancer_service(load_balancer_id=os.getenv('RANCHER_LB_ID'),
                                 protocol=os.getenv('RANCHER_LB_PROTOCOL', "http"),
                                 hostname=os.getenv('ENV_DOMAIN'),
                                 sourcePort=int(os.getenv('EXTERNAL_PORT', 80)),
                                 targetPort=int(os.getenv('INTERNAL_PORT', 80)),
                                 serviceId=os.getenv('RANCHER_SVC_ID'),
                                 portType=os.getenv('RANCHER_LB_TYPE', "portRule"),
                                 RANCHER_PROJECT_ID=os.getenv('RANCHER_PROJECT_ID')
                                 ):
    """Update load balancer target"""
    lb_config = __get_lb_service(load_balancer_id)
    seen = []
    new_portRules = []
    old_portRules = copy.deepcopy(lb_config["lbConfig"]["portRules"])
    for d in old_portRules:
        t = d.copy()
        priority_not_exist = False
        if 'path' in t:
            if t['path'] is None:
                del t['path']
                priority_not_exist = True
        if 'selector' in t:
            if t['selector'] is None:
                del t['selector']
                priority_not_exist = True
        if 'backendName' in t:
            if t['backendName'] is None:
                del t['backendName']
                priority_not_exist = True
        if priority_not_exist:
            del t['priority']
        if t not in seen:
            seen.append(t)
            new_portRules.append(d)

    lb_config["lbConfig"]["portRules"] = new_portRules

    payload = merge(lb_config,
                    {"lbConfig":
                         {"portRules": [{"protocol": protocol,
                                         "type": portType,
                                         "hostname": hostname,
                                         "sourcePort": sourcePort,
                                         "targetPort": targetPort,
                                         "serviceId": serviceId}
                                        ]
                          }
                     })
    end_point = '{}/projects/{}/loadbalancerservices/{}'.format(
        V2_BETA, RANCHER_PROJECT_ID, load_balancer_id)
    response = put(end_point, payload)
    if response.status_code not in range(200, 300):
        print('Not update lb config:', response.text)
    print(f"{hostname}:{sourcePort}")


if __name__ == '__main__':
    update_load_balancer_service()
