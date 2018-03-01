from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from store.es import ElasticsearchStorage

store = ElasticsearchStorage()
store.create_db()

scheduler = AsyncIOScheduler(timezone="UTC")
scheduler.add_job(store.cleanup_db, 'interval', seconds=15)
scheduler.add_job(store.update_db, 'interval', seconds=10)
scheduler.start()

app = web.Application()


async def handle(request):
    name = request.match_info.get('name', "Anonymous")
    text = "Hello, " + name
    return web.Response(text=text)


web.run_app(app)
