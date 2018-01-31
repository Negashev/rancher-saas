import os

import socketio
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from store.es import ElasticsearchStorage
from store.ignite import IgniteStorage

# store = IgniteStorage(os.getenv('IGNITE_HOST', 'ignite'))
store = ElasticsearchStorage()
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


web.run_app(app)
