import os
import shutil

import time

import re
from subprocess import call, check_output
from flask import Flask
from flask_apscheduler import APScheduler

from hacks import mkdir_with_chmod, get_dirs, last_modify_file
from rancher_update_lb import update_load_balancer_service
from scheduler import Config

app = Flask(__name__)
app.app_root = os.path.dirname(os.path.abspath(__file__))
app.lock = False
root = '/'


def prepare_compose(service_name, compose_file):
    print(f"create {os.path.join(root, 'tmp', compose_file)} by {os.path.join(app.app_root, 'compose', compose_file)}")
    with open(os.path.join(app.app_root, 'compose', compose_file), 'r') as compose:
        data = compose.read()
        data = re.sub("SERVICE_NAME", f"service-{service_name}", data)
        data = re.sub("SERVICE_IMAGE", os.getenv('SERVICE_IMAGE', 'nginx:alpine'), data)
        data = re.sub("SERVICE_NFS_VOLUME", os.getenv('SERVICE_NFS_VOLUME', f'mounted') + f'/{service_name}', data)
        data = re.sub("SERVICE_VOLUME", os.getenv('SERVICE_VOLUME', '/usr/share/nginx/html'), data)
        data = re.sub("INTERNAL_PORT", os.getenv('INTERNAL_PORT', '80'), data)
        data = re.sub("SERVICE_TIMEOUT", os.getenv('SERVICE_TIMEOUT', '60000'), data)
        with open(os.path.join(root, 'tmp', compose_file), 'w') as new_compose:
            new_compose.write(data)


@app.route('/')
def make_data():
    if app.lock:
        return 'Create db in another process, please wait a bit', 400
    app.lock = True
    try:
        mounted_path = mkdir_with_chmod('mounted')
        source_path = mkdir_with_chmod('source')
        blanks_path = mkdir_with_chmod('blanks')
        this_time = time.time()
        with open(os.path.join(source_path, '.uuid'), 'r') as source:
            source_uuid = source.read()
        blanks_dirs = get_dirs(blanks_path)
        for blank_dir in blanks_dirs:
            try:
                with open(os.path.join(blank_dir, '.uuid'), 'r') as f:
                    blank_uuid = f.read()
                    # if uuid update (new source data)
                    if source_uuid == blank_uuid:
                        uuid = os.path.basename(blank_dir)
                        # move data with first update!
                        with open(os.path.join(blank_dir, f'.move_{blank_uuid}'), 'w') as out:
                            out.write(str(this_time))
                        shutil.move(blank_dir, os.path.join(mounted_path, uuid))
                        # create compose files!
                        prepare_compose(uuid, 'docker-compose.yml')
                        prepare_compose(uuid, 'rancher-compose.yml')
                        # add storage!
                        call([
                            "rancher",
                            "volume",
                            "create",
                            "--driver",
                            "rancher-nfs",
                            os.getenv('SERVICE_NFS_VOLUME', f'mounted') + f'/{uuid}'
                        ])
                        # add service!
                        call([
                            "rancher",
                            "-f",
                            os.path.join(root, 'tmp', 'docker-compose.yml'),
                            "--rancher-file",
                            os.path.join(root, 'tmp', 'rancher-compose.yml'),
                            "up",
                            "-d"
                        ])
                        # get service id for LB
                        RANCHER_SVC_ID = check_output(
                            ["rancher",
                             "ps",
                             "|",
                             "grep",
                             f"{os.getenv('COMPOSE_PROJECT_NAME')}/service-{uuid}",
                             "|",
                             "awk",
                             "'{print $1}'"])
                        # update lb
                        update_load_balancer_service(serviceId=RANCHER_SVC_ID,
                                                     hostname=f"service-{uuid}.{os.getenv('ENV_DOMAIN')}")
                        app.lock = False
                        return uuid
            except Exception as e:
                app.lock = False
                return e, 401
    except Exception as e:
        print(e)
    app.lock = False
    return 'There is no free blank, please wait a bit', 402


if __name__ == '__main__':
    app.config.from_object(Config())

    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()

    app.run(
        host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', 80)),
        debug=bool(os.getenv('DEBUG', False))
    )
