import os
import uuid

import socketio
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from store.ignite import IgniteStorage

store = IgniteStorage(os.getenv('IGNITE_HOST', 'ignite'))
store.create_db()

scheduler = AsyncIOScheduler(timezone="UTC")
scheduler.add_job(store.cleanup_db, 'interval', seconds=15)
scheduler.start()

# mgr = socketio.AsyncRedisManager(os.getenv('REDIS_URL', 'redis://redis:6379/0'))
sio = socketio.AsyncServer(async_mode='aiohttp'
                           # , client_manager=mgr
                           )
app = web.Application()
sio.attach(app)


async def handle(request):
    name = request.match_info.get('name', "Anonymous")
    text = "Hello, " + name
    return web.Response(text=text)


async def delivery(request):
    _uuid = request.match_info.get('uuid', None)
    if _uuid is None:
        return web.Response(text='please use /delivery/{uuid}')
    return web.Response(text=_uuid)


@sio.on('get uuid', namespace='/saas')
async def saas_get_uuid(sid):
    _uuid = str(uuid.uuid4())
    await sio.emit('set uuid', sid, room=sid, namespace='/saas')


@sio.on('delivery', namespace='/saas')
async def saas_delivery(sid, data):
    data.update({"directory": store.delivery_dir(data['uuid'])})
    await sio.emit('delivery', data, room=sid, namespace='/saas')


@sio.on('waiting', namespace='/saas')
async def saas_waiting(sid, data):
    data.update({"address": store.get_address(data['uuid'])})
    await sio.emit('waiting', data, room=sid, namespace='/saas')


@sio.on('health check', namespace='/saas')
async def saas_health_check(sid, address):
    await sio.emit('health check', store.get_uuid_by_address(address), room=sid, namespace='/saas')


@sio.on('ping', namespace='/saas')
async def saas_ping(sid, address):
    store.ping_address(address)
    await sio.emit('ping', address, room=sid, namespace='/saas')

@sio.on('ping tmp', namespace='/saas')
async def saas_tmp_ping(sid, address):
    store.ping_tmp_address(address)
    await sio.emit('ping tmp', address, room=sid, namespace='/saas')


@sio.on('disconnect', namespace='/saas')
async def saas_disconnect(sid):
    await sio.close_room(sid, namespace='/saas')


app.router.add_get('/', handle)
app.router.add_get('/delivery/{uuid}', handle)

web.run_app(app)
