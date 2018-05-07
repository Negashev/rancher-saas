import copy
import json
import os
import random
import time
from hashlib import sha1

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from japronto import Application
from nats.aio.client import Client as NATS

SERVICE_NAME = os.getenv("SERVICE_NAME", "service")
NATS_DSN = os.getenv("NATS_DSN", "nats://nats:4222")
ZPOOL_NAME = os.getenv("ZPOOL_NAME", "zpool1")
UPTIME_TIMEOUT = int(os.getenv("UPTIME_TIMEOUT", 5))

UPTIME_SNAPHOTS = {}
STATUS = {}


async def find_free_server():
    global UPTIME_SNAPHOTS
    servers = copy.deepcopy(UPTIME_SNAPHOTS)
    mounts = 10000000000000000
    this_time = int(time.time()) - UPTIME_TIMEOUT
    most_free_server = None
    equal_free_servers = []
    for i in servers.keys():
        # very new very free server
        len_snapshots = len(servers[i]['snapshots'])
        print(i)
        if not servers[i]['block'] and servers[i]['prepare'] is None and servers[i]['uptime'] >= this_time and len_snapshots <= mounts:
        # if servers[i]['uptime'] >= this_time and len_snapshots <= mounts:
            if mounts == len_snapshots:
                equal_free_servers.append(most_free_server)
                equal_free_servers.append(i)
            elif len_snapshots < mounts:
                # reset free servers
                equal_free_servers = []
            mounts = len_snapshots
            most_free_server = i
    if len(equal_free_servers):
        return random.choice(list(set(equal_free_servers)))
    else:
        return most_free_server


# urls
async def get_version(request):
    return request.Response(text='2')


async def api_find_free_server(request):
    return request.Response(json={"message": await find_free_server()},
                            code=200 if request.nc.is_connected else 500)

async def list_services(request):
    global UPTIME_SNAPHOTS
    return request.Response(json=UPTIME_SNAPHOTS,
                            code=200 if request.nc.is_connected else 500)


async def check_service_uuid(request):
    snapshot_name = f"{ZPOOL_NAME}/from-snapshot-{SERVICE_NAME}-{request.match_dict['uuid']}"
    all_snapshots = copy.deepcopy(UPTIME_SNAPHOTS)
    for server in all_snapshots.keys():
        if snapshot_name in all_snapshots[server]['snapshots'].keys():
            snapshot = all_snapshots[server]['snapshots'][snapshot_name]
            return request.Response(json=snapshot,
                                    code=200 if request.nc.is_connected else 500)
    return request.Response(json={"error": f"Service {request.match_dict['uuid']} not found"},
                            code=200 if request.nc.is_connected else 500)


async def service_status(request):
    _sha1 = request.match_dict['sha1']
    data = {"error": f"Not found status for {_sha1}"}
    code = 400
    if _sha1 in STATUS:
        data = STATUS[_sha1]
        code = 200
    return request.Response(json=data,
                            code=code if request.nc.is_connected else 500)


async def find_service_uuid(request):
    uuid = request.match_dict['uuid']
    data = sha1(uuid.encode('utf-8')).hexdigest()
    free_server = await find_free_server()
    if free_server:
        await request.nc.publish(f"{SERVICE_NAME}-delivery-{free_server}", bytes(data, 'utf-8'))
        return request.Response(json={"message": f"Delivery '{data}' on '{free_server}' SAAS server"},
                                code=200 if request.nc.is_connected else 500)
    return request.Response(json={"error": "SAAS servers not found"},
                            code=501 if request.nc.is_connected else 500)


async def service_uptime(request):
    match_dict = request.match_dict
    this_time = 1800
    if 'time' in match_dict.keys():
        this_time = int(match_dict['time'])
    await nc.publish(f"{SERVICE_NAME}-uptime",
                     bytes(
                         json.dumps(
                             {
                                 "mount": f"{ZPOOL_NAME}/from-snapshot-{SERVICE_NAME}-{match_dict['sha1']}",
                                 "time": this_time
                             }
                         ),
                         'utf-8'))
    return request.Response(text='ok',
                            code=200 if request.nc.is_connected else 500)


async def cleanup_service(request):
    if request.nc.is_connected:
        await request.nc.publish(f"{SERVICE_NAME}-cleanup-service", bytes(request.match_dict['sha1'], 'utf-8'))
    return request.Response(text='send', code=200 if request.nc.is_connected else 500)


# subscribe
async def mounted(msg):
    global UPTIME_SNAPHOTS
    data = json.loads(msg.data.decode())
    data.update({"uptime": int(time.time())})
    UPTIME_SNAPHOTS[data['hostname']] = data


async def update_status(msg):
    global STATUS
    this_time = int(time.time())
    data = json.loads(msg.data.decode())
    data.update({"uptime": this_time})
    STATUS[data['sha1']] = data


async def cleanup_status(msg):
    global STATUS
    data = msg.data.decode()
    try:
        print(f"Remove status for {data}")
        del STATUS[data]
    except Exception as e:
        pass


# scheduler
async def remove_sleep_servers():
    global UPTIME_SNAPHOTS
    this_time = int(time.time()) - 30
    servers = copy.deepcopy(UPTIME_SNAPHOTS)
    for i in servers.keys():
        if UPTIME_SNAPHOTS[i]['uptime'] < this_time:
            print(f"server {i} is offline")
            del UPTIME_SNAPHOTS[i]


async def remove_sleep_statuses():
    global STATUS
    this_time = int(time.time()) - 600
    statuses = copy.deepcopy(STATUS)
    for i in statuses.keys():
        if STATUS[i]['uptime'] < this_time:
            print(f"Remove status for {i}")
            del STATUS[i]


# init
async def connect_nats(app):
    await nc.connect(servers=[NATS_DSN], io_loop=app.loop, max_reconnect_attempts=-1, verbose=True)
    await nc.subscribe(f"{SERVICE_NAME}-mounted", cb=mounted)
    await nc.subscribe(f"{SERVICE_NAME}-status", cb=update_status)
    await nc.subscribe(f"{SERVICE_NAME}-cleanup-status", cb=cleanup_status)
    # add nats to japronto app
    app.extend_request(lambda x: nc, name='nc', property=True)


async def connect_scheduler():
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(remove_sleep_servers, 'interval', seconds=1)
    scheduler.add_job(remove_sleep_statuses, 'interval', seconds=1)
    scheduler.start()


app = Application()
nc = NATS()
app.loop.run_until_complete(connect_nats(app))
app.loop.run_until_complete(connect_scheduler())
router = app.router
router.add_route('/', list_services)
router.add_route('/version', get_version)
router.add_route('/status/{sha1}', service_status)
router.add_route('/check/{uuid}', check_service_uuid)
router.add_route('/find/{uuid}', find_service_uuid)
router.add_route('/uptime/{sha1}', service_uptime)
router.add_route('/uptime/{sha1}/{time}', service_uptime)
router.add_route('/cleanup/{sha1}', cleanup_service)
router.add_route('/find_free_server', api_find_free_server)
app.run(debug=bool(int(os.getenv('DEBUG', 0))))
