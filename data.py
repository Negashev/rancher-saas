import asyncio
import json
import os
import re
import socket
import time

import requests
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError
from japronto import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from weir import zfs, process
from nats.aio.client import Client as NATS
from weir.process import DatasetExistsError

from sweet_hacks import last_modify_file, mkdir_with_chmod, recursive_copy_and_sleep, get_size

SLEEP_TIME = float(os.getenv("SLEEP_TIME", 0.5))
ZPOOL_NAME = os.getenv("ZPOOL_NAME", "zpool1")
ZPOOL_MOUNT = os.getenv("ZPOOL_MOUNT", "/mnt")
SERVICE_NAME = os.getenv("SERVICE_NAME", "service")
DATA_SOURCE = os.getenv("DATA_SOURCE", "/source")
NATS_DSN = os.getenv("NATS_DSN", "nats://nats:4222")
DATA_SOURCE_FREEZE_TIME = 60 * 60 * int(os.getenv("DATA_SOURCE_FREEZE_TIME", 26))  # default 26 hours
HOSTNAME = os.getenv("HOSTNAME", socket.gethostname())

# for docker container
SERVICE_IMAGE = os.getenv('SERVICE_IMAGE', 'nginx:alpine')
SERVICE_PORT = os.getenv('SERVICE_PORT', "80/tcp")
SERVICE_VOLUME = os.getenv('SERVICE_VOLUME', "/usr/share/nginx/html")

LOCK = False
FIRST_INIT = False
UPTIME_SNAPSHOTS = {}
IGNORE_SNAPSHOT = None
# first init
DATA_SOURCE_TIME = 10000000000000000


def find_service_dirs():
    data_dirs = []
    for i in zfs.find(ZPOOL_NAME):
        # find if zpool/from-snapshot-service-*
        if not i.name.startswith(f"{ZPOOL_NAME}/from-snapshot-{SERVICE_NAME}-"):
            continue
        data_dirs.append(i)
    return data_dirs


def get_container_hostdata(host_data):
    if 'USE_IP_ADDR' in os.environ:
        host_data['HostIp'] = os.getenv('USE_IP_ADDR')
    if 'USE_RANCHER' in os.environ:
        r = requests.get('http://rancher-metadata/latest/self/host/agent_ip',
                         headers={'Accept': 'application/json'})
        host_data['HostIp'] = r.json()
    return host_data


async def container_by_data(container, const_find_service_dirs):
    global UPTIME_SNAPSHOTS
    container_names = container._container['Names']
    for i in const_find_service_dirs:
        tmp_container_name = re.sub(rf"^({ZPOOL_NAME}/from-snapshot-)", "/", i.name)
        if tmp_container_name in container_names:
            # resolve all date for this container
            await container.show()
            # get port
            container_port = await container.port(SERVICE_PORT)
            host_data = get_container_hostdata(container_port[0])
            UPTIME_SNAPSHOTS[i.name] = {"uptime": int(time.time()) + 1800,
                                        "address": f"{host_data['HostIp']}:{host_data['HostPort']}"}


async def datanode_first_up():
    docker = Docker()
    const_find_service_dirs = find_service_dirs()
    for container in (await docker.containers.list()):
        await container_by_data(container, const_find_service_dirs)
    await docker.close()


def find_data_source(with_snapshots=True):
    global LOCK
    '''
    :return: data_source: list[ZFSFilesystem]
    '''
    if LOCK:
        return None
    data_source = []
    for i in zfs.find(ZPOOL_NAME):
        # find if zpool/service-*
        if not i.name.startswith(f"{ZPOOL_NAME}/{SERVICE_NAME}-"):
            continue
        if i.name == IGNORE_SNAPSHOT:
            continue
        snapshots = i.snapshots()
        if not snapshots and with_snapshots:
            continue
        if with_snapshots and snapshots[0].snapname() != 'snapshot':
            continue
        data_source.append(i)
    return data_source


def with_sort(data_source, reverse=True):
    global LOCK
    global DATA_SOURCE_TIME
    '''
    :param data_source: list[ZFSFilesystem]
    :param reverse: bool
    :return: sort_data: list[ZFSFilesystem]
    '''
    if LOCK:
        return None
    data_source.sort(key=lambda x: x.name, reverse=reverse)
    if reverse:
        if len(data_source):
            DATA_SOURCE_TIME = int(re.sub(rf"^({ZPOOL_NAME}/{SERVICE_NAME}-)", "", data_source[0].name))
            return data_source[0]
    else:
        # find oldest source data (but stay one)
        if len(data_source) >= 2:
            return data_source[:-1]
    return None


def create_data_snapshot():
    global LOCK
    global IGNORE_SNAPSHOT
    global FIRST_INIT
    global DATA_SOURCE_TIME
    this_time = int(time.time())
    new_zfs_name = f"{ZPOOL_NAME}/{SERVICE_NAME}-{this_time}"
    LOCK = True
    IGNORE_SNAPSHOT = new_zfs_name
    print(f"Creating {new_zfs_name}")
    new_zfs = zfs.create(new_zfs_name)
    print(f"Copy data to {new_zfs.name}")
    recursive_copy_and_sleep(SLEEP_TIME, DATA_SOURCE, mkdir_with_chmod(f"{ZPOOL_MOUNT}/{new_zfs.name}"))
    print(f"Make snapshot {new_zfs_name}")
    new_zfs.snapshot('snapshot')
    # set DATA_SOURCE_TIME for
    DATA_SOURCE_TIME = int(re.sub(rf"^({ZPOOL_NAME}/{SERVICE_NAME}-)", "", new_zfs.name))
    IGNORE_SNAPSHOT = None
    FIRST_INIT = True
    LOCK = False


def check_create_data_snapshot():
    global LOCK
    global IGNORE_SNAPSHOT
    global FIRST_INIT
    try:
        this_time = time.time()
        newer_file, newer_time = last_modify_file(DATA_SOURCE)
        if newer_time is None:
            return
        if this_time - newer_time < 60.0:
            return
        for dirpath, dirnames, files in os.walk(DATA_SOURCE):
            if not files:
                return
        data_source = with_sort(find_data_source())
        if data_source is None:
            create_data_snapshot()
            return
        if get_size(DATA_SOURCE) != get_size(f"{ZPOOL_MOUNT}/{data_source.name}"):
            create_data_snapshot()
            return
    except Exception as e:
        print(e)
    FIRST_INIT = True
    IGNORE_SNAPSHOT = None
    LOCK = False


def destroy_data_snapshot():
    global LOCK
    if LOCK:
        return None
    oldest_zfs = with_sort(find_data_source(with_snapshots=False), reverse=False)
    if oldest_zfs is None:
        return
    for i in oldest_zfs:
        # Start destroy i.name
        for snapshot in i.snapshots():
            snapshot.destroy(defer=True)
        try:
            i.destroy()
            print(f"Destroy {i.name}")
        except Exception as e:
            print(f"Can't destroy {i.name}")


async def store_services():
    global UPTIME_SNAPSHOTS
    global LOCK
    global FIRST_INIT
    await nc.publish(f"{SERVICE_NAME}-mounted",
                     bytes(json.dumps({"hostname": HOSTNAME, "snapshots": UPTIME_SNAPSHOTS, "block": LOCK,
                                       "prepare": IGNORE_SNAPSHOT, "data_source_time": DATA_SOURCE_TIME, "first_init": FIRST_INIT}), 'utf-8'))


async def uptime_handler(msg):
    global UPTIME_SNAPSHOTS
    data = json.loads(msg.data.decode())
    try:
        UPTIME_SNAPSHOTS[data['mount']].update({"uptime": int(time.time()) + data['time']})
    except Exception as e:
        pass


async def delivery_handler(msg):
    # ping status NC
    data = msg.data.decode()
    await nc.publish(f"{SERVICE_NAME}-status", bytes(json.dumps({"sha1": data, "message": "start delivery"}), "utf-8"))
    data_source = with_sort(find_data_source())
    if data_source is None:
        await nc.publish(f"{SERVICE_NAME}-status",
                         bytes(json.dumps({"sha1": data, "error": "Data source not found"}), "utf-8"))
        return
    print(f"Create {data} to mounted")
    await nc.publish(f"{SERVICE_NAME}-status",
                     bytes(json.dumps({"sha1": data, "message": f"Create {data} to mounted"}), "utf-8"))

    url = zfs._urlsplit(data_source.name + '@snapshot')

    cmd = ['zfs', 'clone']

    cmd.append(url.path)

    clone_name = f"{ZPOOL_NAME}/from-snapshot-{SERVICE_NAME}-{data}"
    UPTIME_SNAPSHOTS[clone_name] = {"uptime": int(time.time()) + 300}
    await store_services()

    cmd.append(clone_name)
    try:
        process.check_call(cmd, netloc=url.netloc)
    except DatasetExistsError as e:
        print(e)
        await nc.publish(f"{SERVICE_NAME}-status",
                         bytes(json.dumps({"sha1": data, "error": f"Snapshot for {data} exist"}), "utf-8"))
        return

    clone_name_zfs = zfs.ZFSVolume(clone_name)

    print(f"Make container {SERVICE_NAME}-{data}")
    await nc.publish(f"{SERVICE_NAME}-status",
                     bytes(json.dumps({"sha1": data, "message": f"Make container {SERVICE_NAME}-{data}"}), "utf-8"))

    config = {
        "Image": SERVICE_IMAGE,
        "AttachStdin": False,
        "AttachStdout": True,
        "AttachStderr": True,
        "Tty": False,
        "OpenStdin": False,
        "StdinOnce": False,
        "ExposedPorts": {SERVICE_PORT: {}},
        "PortBindings": {SERVICE_PORT: [{'HostPort': None}]},
        "Binds": [f"{os.path.join(ZPOOL_MOUNT, clone_name)}:{SERVICE_VOLUME}"],
        "Env": [f"{i[12:]}={os.getenv(i)}" for i in os.environ if i.startswith('SERVICE_ENV_')]

    }
    if 'SERVICE_CMD' in os.environ:
        config.update({"Cmd": os.getenv('SERVICE_CMD').split(' ')})
    docker = Docker()
    try:
        await docker.images.get(SERVICE_IMAGE)
    except DockerError as e:
        if e.status == 404:
            print(f"Pull image {SERVICE_IMAGE}")
            await nc.publish(f"{SERVICE_NAME}-status",
                             bytes(json.dumps({"sha1": data, "message": f"Pull image {SERVICE_IMAGE} on '{HOSTNAME}'"}),
                                   "utf-8"))
            await docker.pull(SERVICE_IMAGE)
        else:
            print(f'Error retrieving {SERVICE_IMAGE} image.')
            await nc.publish(f"{SERVICE_NAME}-status",
                             bytes(json.dumps(
                                 {"sha1": data, "error": f"Error retrieving {SERVICE_IMAGE} image on '{HOSTNAME}'"}),
                                 "utf-8"))
            clone_name_zfs.destroy(defer=True)
            return
    try:
        print(f"Create container {SERVICE_NAME}-{data}")
        await nc.publish(f"{SERVICE_NAME}-status",
                         bytes(json.dumps({"sha1": data, "message": f"Create container {SERVICE_NAME}-{data}"}),
                               "utf-8"))
        container = await docker.containers.create_or_replace(config=config, name=f"{SERVICE_NAME}-{data}")
        print(f"Start container {SERVICE_NAME}-{data}")
        await nc.publish(f"{SERVICE_NAME}-status",
                         bytes(json.dumps({"sha1": data, "message": f"Start container {SERVICE_NAME}-{data}"}),
                               "utf-8"))
        await container.start()

        # get output port
        print(f"Get port for {SERVICE_NAME}-{data}")
        await nc.publish(f"{SERVICE_NAME}-status",
                         bytes(json.dumps({"sha1": data, "message": f"Get port for {SERVICE_NAME}-{data}"}), "utf-8"))
        container_port = await container.port(SERVICE_PORT)
        await docker.close()
        host_data = get_container_hostdata(container_port[0])

        UPTIME_SNAPSHOTS[clone_name] = {"uptime": int(time.time()) + 60,
                                        "address": f"{host_data['HostIp']}:{host_data['HostPort']}"}
        # ping uptime
        await store_services()
        print(f"Done {data}")
        await nc.publish(f"{SERVICE_NAME}-status", bytes(
            json.dumps({"sha1": data, "message": f"Done {data} on {host_data['HostIp']}:{host_data['HostPort']}",
                        "address": f"{host_data['HostIp']}:{host_data['HostPort']}",
                        "uuid": data}), "utf-8"))

        return
    except Exception as e:
        # drop storage if errors
        await docker.close()
        clone_name_zfs.destroy(defer=True)
        await nc.publish(f"{SERVICE_NAME}-status", bytes(
            json.dumps({"sha1": data, "error": f"Can's start container {SERVICE_NAME}-{data} image."}), "utf-8"))


async def cleanup_service(msg):
    global UPTIME_SNAPSHOTS
    data = msg.data.decode()
    docker = Docker()
    for container in (await docker.containers.list()):
        if f"/{SERVICE_NAME}-{data}" in container._container['Names']:
            print(f"Remove container {SERVICE_NAME}-{data}")
            await container.delete(force=True)
    await docker.close()
    # wait container is remove
    remove = 0
    while remove > 10:
        try:
            await asyncio.sleep(1)
            snapshot = zfs.ZFSVolume(f"{ZPOOL_NAME}/from-snapshot-{SERVICE_NAME}-{data}")
            await snapshot.destroy()
            remove = 11
        except Exception as e:
            remove = remove + 1
    print(f"Cleanup snapshot {snapshot.name}")

    await nc.publish(f"{SERVICE_NAME}-cleanup-status", bytes(msg, "utf-8"))
    del UPTIME_SNAPSHOTS[f"{ZPOOL_NAME}/from-snapshot-{SERVICE_NAME}-{data}"]
    await store_services()
    return


# url
async def list_services(request):
    global UPTIME_SNAPSHOTS
    global FIRST_INIT
    if FIRST_INIT:
        #  if DATA_SOURCE_TIME is more 26 hours (93600 seconds)
        return request.Response(json=UPTIME_SNAPSHOTS,
                                code=200 if request.nc.is_connected and DATA_SOURCE_TIME > (
                                        int(time.time()) - DATA_SOURCE_FREEZE_TIME) else 500)
    else:
        return request.Response(json=UPTIME_SNAPSHOTS,
                                code=200 if request.nc.is_connected else 500)


async def remove_sleep_docker(snapshot):
    docker = Docker()
    for container in (await docker.containers.list()):
        tmp_container_name = re.sub(rf"^({ZPOOL_NAME}/from-snapshot-)", "/", snapshot.name)
        if tmp_container_name in container._container['Names']:
            print(f"Drop container {tmp_container_name} ({container._id})")
            await container.delete(force=True)
    await docker.close()
    print(f"Remove {snapshot.name}")
    try:
        await snapshot.destroy()
    except Exception as e:
        print(f"Can't remove {snapshot.name}")
    return


async def remove_sleep():
    global UPTIME_SNAPSHOTS
    const_find_service_dirs = find_service_dirs()
    for i in const_find_service_dirs:
        # if this storage have mount service
        this_time = time.time()
        if i.name in UPTIME_SNAPSHOTS:
            if UPTIME_SNAPSHOTS[i.name]['uptime'] < int(this_time):
                await remove_sleep_docker(i)
                del UPTIME_SNAPSHOTS[i.name]
        else:
            print(f"Remove {i.name}")
            i.destroy()
            await nc.publish(f"{SERVICE_NAME}-cleanup-status",
                             bytes(re.sub(rf"^({ZPOOL_NAME}/from-snapshot-{SERVICE_NAME}-)", "", i.name), "utf-8"))
            return


# init
async def connect_nats(app):
    await nc.connect(servers=[NATS_DSN], io_loop=app.loop, max_reconnect_attempts=-1, verbose=True)
    await nc.subscribe(f"{SERVICE_NAME}-uptime", cb=uptime_handler)
    await nc.subscribe(f"{SERVICE_NAME}-delivery-{HOSTNAME}", cb=delivery_handler)
    await nc.subscribe(f"{SERVICE_NAME}-cleanup-service", cb=cleanup_service)
    # add nats to japronto app
    app.extend_request(lambda x: nc, name='nc', property=True)


async def connect_scheduler():
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(check_create_data_snapshot, 'interval', seconds=20)
    scheduler.add_job(destroy_data_snapshot, 'interval', seconds=20)

    scheduler.add_job(store_services, 'interval', seconds=1)

    scheduler.add_job(remove_sleep, 'interval', seconds=60)

    scheduler.start()
    # add docker to japronto app
    docker = Docker()
    app.extend_request(lambda x: docker, name='docker', property=True)


async def check_first_init():
    global FIRST_INIT
    data_source = with_sort(find_data_source())
    if data_source is None:
        FIRST_INIT = False
        return
    if get_size(DATA_SOURCE) == get_size(f"{ZPOOL_MOUNT}/{data_source.name}"):
        FIRST_INIT = True
        return


app = Application()
nc = NATS()
app.loop.run_until_complete(connect_nats(app))
app.loop.run_until_complete(datanode_first_up())
app.loop.run_until_complete(check_first_init())
app.loop.run_until_complete(store_services())
app.loop.run_until_complete(connect_scheduler())
router = app.router
router.add_route('/', list_services)
app.run(debug=bool(int(os.getenv('DEBUG', 0))))
