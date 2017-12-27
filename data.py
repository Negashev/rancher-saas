import shutil
import socket
import uuid

import time
import os

import requests
import socketio
from aiohttp import web
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from store.ignite import IgniteStorage
from sweet_hacks import mkdir_with_chmod, get_dirs, last_modify_file, get_size

mount_lock = False
'''
    Create all blanks
'''


def create_blanks():
    blanks_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'blanks'))
    tmp_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'tmp'))
    source_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'source'))
    # get ready blanks
    blanks_dirs = get_dirs(blanks_path)
    # check if we need new blank
    if len(blanks_dirs) >= int(os.getenv('BLANKS', 5)):
        return
    # check space
    statvfs = os.statvfs(os.getenv('DATA_DIR'))
    if statvfs.f_frsize * statvfs.f_bfree * 1e-9 < float(os.getenv('FREE_SPACE_RESERVE', 20.0)):
        return
    this_time = time.time()
    # if source data not ready
    newer_file, newer_time = last_modify_file(source_path)
    if newer_time is None:
        return
    if this_time - newer_time < 20.0:
        return
    # create new path for blank
    new_dir = str(uuid.uuid4())
    new_tmp_dir = os.path.join(tmp_path, new_dir)
    new_path = os.path.join(blanks_path, new_dir)
    print(f"create {new_tmp_dir}")
    # copy data
    shutil.copytree(source_path, new_tmp_dir)
    os.chmod(new_tmp_dir, 0o777)
    if get_size(source_path) == get_size(new_tmp_dir):
        # move data!
        print(f"move {new_tmp_dir} {new_path}")
        shutil.move(new_tmp_dir, new_path)


'''
    Check broken or old blanks
'''


def check_blanks():
    blanks_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'blanks'))
    source_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'source'))
    this_time = time.time()
    # if source data not ready
    newer_file, newer_time = last_modify_file(source_path)
    if newer_time is None:
        return
    if this_time - newer_time < 20.0:
        return
    # get ready blanks
    blanks_dirs = get_dirs(blanks_path)
    remove_uuid = None

    newer_file, newer_time = last_modify_file(source_path)
    if newer_time is None:
        return
    if this_time - newer_time < 60.0:
        return
    # check all blanks
    for blank_dir in blanks_dirs:
        if remove_uuid is not None:
            break
        try:
            # if this cold dir
            newer_file, newer_time = last_modify_file(blank_dir)
            if newer_time is None:
                continue
            if this_time - newer_time < 60.0:
                continue
            # if size not valid
            if get_size(source_path) != get_size(blank_dir):
                remove_uuid = blank_dir
        except Exception as e:
            print(e)
            try:
                # if this broken blank remove them
                newer_file, newer_time = last_modify_file(blank_dir)
                if newer_time is None:
                    continue
                if this_time - newer_time < 60.0:
                    continue
                remove_uuid = blank_dir
            except Exception as e:
                print(e)
    if remove_uuid is not None:
        uuid = os.path.basename(remove_uuid)
        print(f'remove {uuid}')
        shutil.move(remove_uuid, os.path.join(os.getenv('DATA_DIR'), 'tmp', uuid))


'''
    Remove freeze tmp clones
'''


def clean_tmp():
    tmp_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'tmp'))
    tmp_dirs = get_dirs(tmp_path)
    this_time = time.time()
    for tmp_dir in tmp_dirs:
        # if this cold dir very long
        newer_file, newer_time = last_modify_file(tmp_dir)
        if newer_time is None:
            shutil.rmtree(tmp_dir)
            continue
        if this_time - newer_time > 60.0 * 5:
            print(f'remove freeze tmp {tmp_dir}')
            shutil.rmtree(tmp_dir)


'''
    Ping blanks and mounted dirs in store
'''


def store_dirs():
    this_time = time.strftime('%Y-%m-%d %H:%M:%S')
    hostname = socket.gethostname()
    blanks_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'blanks'))
    mounted_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'mounted'))

    store.set_dirs([os.path.basename(i) for i in get_dirs(blanks_path)], hostname, 'blanks', this_time)

    store.set_dirs([os.path.basename(i) for i in get_dirs(mounted_path)], hostname, 'mounted', this_time)


async def check_for_create_service_with_storage():
    global mount_lock
    mount_lock = True
    blanks_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'blanks'))
    directory, delivery = store.get_directory_for_move([os.path.basename(i) for i in get_dirs(blanks_path)])
    if directory is None:
        mount_lock = False
        return
    mounted_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'mounted'))
    print(f"move {directory} to mounted")
    print(f"move {os.path.join(blanks_path, directory)} to {os.path.join(mounted_path, directory)}")
    shutil.move(os.path.join(blanks_path, directory), os.path.join(mounted_path, directory))

    print("make container")
    SERVICE_IMAGE = os.getenv('SERVICE_IMAGE', 'nginx:latest')
    SERVICE_PORT = os.getenv('SERVICE_PORT', "80/tcp")
    SERVICE_VOLUME = os.getenv('SERVICE_VOLUME', "/usr/share/nginx/html")
    DATA_DIR_ON_SERVER = os.path.join(os.getenv('DATA_DIR_ON_SERVER'), 'mounted', directory)
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
        "Binds": [f"{DATA_DIR_ON_SERVER}:{SERVICE_VOLUME}"],
        "Env": [f"{i[12:]}={os.getenv(i)}" for i in os.environ if i.startswith('SERVICE_ENV_')]

    }
    if 'SERVICE_CMD' in os.environ:
        config.update({"Cmd": os.getenv('SERVICE_CMD').split(' ')})
    try:
        await docker.images.get(SERVICE_IMAGE)
    except DockerError as e:
        if e.status == 404:
            await docker.pull(SERVICE_IMAGE)
        else:
            print(f'Error retrieving {SERVICE_IMAGE} image.')
            mount_lock = False
            return
    container = await docker.containers.create_or_replace(config=config, name=directory)
    await container.start()
    # get output port
    containerPort = await container.port(SERVICE_PORT)
    hostData = containerPort[0]
    if 'USE_IP_ADDR' in os.environ:
        hostData['HostIp'] = os.getenv('USE_IP_ADDR')
    if 'USE_RANCHER' in os.environ:
        r = requests.get('http://rancher-metadata/latest/self/host/agent_ip', headers={'Accept': 'application/json'})
        hostData['HostIp'] = r.json()
    # if you don't trust for redis :)
    store.set_address_for_directory(directory, f"{hostData['HostIp']}:{hostData['HostPort']}")
    # if you trust for redis :)
    # await sio.emit('waiting', {'uuid': delivery, "address": f"{hostData['HostIp']}:{hostData['HostPort']}"},
    #                room=delivery, namespace='/saas')
    mount_lock = False


async def check_for_delete_storage_with_service():
    global mount_lock
    mounted_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'mounted'))
    # get all mounted dirs
    mounted_uuid = [os.path.basename(i) for i in get_dirs(mounted_path)]
    if not mounted_uuid:
        return
    mounted_uuid_in_db = store.get_mounted(mounted_uuid)
    # get all sleep dirs
    sleep_directories = store.get_sleep_mounted(mounted_uuid)
    # get all not registered dirs
    filtered_by_mounted_uuid_in_db = list(set(mounted_uuid) - set(mounted_uuid_in_db))

    uuids_to_drop = sleep_directories + filtered_by_mounted_uuid_in_db
    if not uuids_to_drop:
        return
    tmp_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'tmp'))
    # nothink to do of lock!
    if mount_lock:
        return
    for uuid_to_drop in uuids_to_drop:
        for container in (await docker.containers.list()):
            if f"/{uuid_to_drop}" in container._container['Names']:
                print(f"Drop container {container._id}")
                await container.delete(force=True)
        try:
            print(f"move to tmp {os.path.join(mounted_path, uuid_to_drop)} {os.path.join(tmp_path, uuid_to_drop)}")
            shutil.move(os.path.join(mounted_path, uuid_to_drop), os.path.join(tmp_path, uuid_to_drop))
        except Exception as e:
            print(e)
        store.del_mounted(uuid_to_drop)


async def handle(request):
    blanks_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'blanks'))
    mounted_path = mkdir_with_chmod(os.path.join(os.getenv('DATA_DIR'), 'mounted'))

    return web.json_response(get_dirs(blanks_path) + get_dirs(mounted_path))


docker = Docker()
store = IgniteStorage(os.getenv('IGNITE_HOST', 'ignite'))
store.create_db()

scheduler = AsyncIOScheduler(timezone="UTC")
scheduler.add_job(create_blanks, 'interval', seconds=10)
scheduler.add_job(check_blanks, 'interval', seconds=10)
scheduler.add_job(clean_tmp, 'interval', seconds=30)
scheduler.add_job(store_dirs, 'interval', seconds=1)
scheduler.add_job(store.cleanup_db, 'interval', seconds=15)
scheduler.add_job(check_for_create_service_with_storage, 'interval', seconds=2)
scheduler.add_job(check_for_delete_storage_with_service, 'interval', seconds=30)
scheduler.start()

# mgr = socketio.AsyncRedisManager(os.getenv('REDIS_URL', 'redis://redis:6379/0'))
sio = socketio.AsyncServer(async_mode='aiohttp'
                           # , client_manager=mgr
                           )
app = web.Application()
app.router.add_get('/', handle)

web.run_app(app)
