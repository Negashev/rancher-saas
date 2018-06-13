import os
from japronto import Application
from get_service_address import get_service_address
from service_uuid import get_service_uuid


def gsa(request):
    return request.Response(text=get_service_address())

def guuid(request):
    return request.Response(text=get_service_uuid())


# read prefix
f = open('/tmp/prefix.file', 'r')
prefix = f.read()

app = Application()
app.router.add_route('/', gsa)
app.router.add_route('/uuid', guuid)
app.run(host='0.0.0.0', port=int(os.getenv(f'{prefix}IP_SERVICE_PORT', 8080)))
