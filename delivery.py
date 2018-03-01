from aiohttp import web

from store.es import ElasticsearchStorage

store = ElasticsearchStorage()
store.create_db()
app = web.Application()

async def handle(request):
    return web.json_response(store.get_all_mounted())


async def delivery(request):
    _uuid = request.match_info.get('uuid', None)
    if _uuid is None:
        return web.json_response({'error': 'please use /delivery/{uuid}'})
    return web.json_response({"directory": store.delivery_dir(_uuid)})


async def waiting(request):
    _uuid = request.match_info.get('uuid', None)
    if _uuid is None:
        return web.json_response({'error': 'please use /waiting/{uuid}'})
    return web.json_response({"address": store.get_address(_uuid)})


async def health_check(request):
    address = request.match_info.get('address', None)
    if address is None:
        return web.json_response({'error': 'please use /health_check/{address}'})
    return web.json_response({"uuid": store.get_uuid_by_address(address)})


async def ping(request):
    ping_type = request.match_info.get('ping_type', None)
    _uuid = request.match_info.get('uuid', None)
    if ping_type is None or _uuid is None:
        return web.json_response({'error': 'please use /ping/{ping_type}/{uuid}'})
    if ping_type == 'stable':
        return web.json_response(store.ping_uuid(_uuid))
    else:
        return web.json_response(store.ping_tmp_uuid(_uuid))

app.router.add_get('/', handle)
app.router.add_get('/delivery/{uuid}', delivery)
app.router.add_get('/waiting/{uuid}', waiting)
app.router.add_get('/health_check/{address}', health_check)
app.router.add_get('/ping/{ping_type}/{uuid}', ping)

web.run_app(app)
