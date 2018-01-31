import os
from japronto import Application
from get_service_address import get_service_address


def gsa(request):
    return request.Response(text=get_service_address())


app = Application()
app.router.add_route('/', gsa)
app.run(host='0.0.0.0', port=int(os.getenv('IP_SERVICE_PORT', 8080)))
