import glob
import os
import time
import uuid
import shutil
from subprocess import call

from hacks import mkdir_with_chmod, get_dirs


class Config(object):
    SCHEDULER_TIMEZONE = 'UTC'
    JOBS = [
        {
            'id': 'create_blanks',
            'func': 'scheduler:create_blanks',
            'trigger': 'interval',
            'seconds': 15,
            'max_instances': 1
        },
        {
            'id': 'check_blanks',
            'func': 'scheduler:check_blanks',
            'trigger': 'interval',
            'seconds': 15,
            'max_instances': 1
        },
        {
            'id': 'clean_mounted',
            'func': 'scheduler:clean_mounted',
            'trigger': 'interval',
            'seconds': 15,
            'max_instances': 1
        }
    ]

    SCHEDULER_API_ENABLED = True


'''
    Create all blanks
'''


def create_blanks():
    blanks_path = mkdir_with_chmod('blanks')
    # get ready blanks
    blanks_dirs = get_dirs(blanks_path)
    # check if we need new blank
    if len(blanks_dirs) >= int(os.getenv('BLANKS', 10)):
        return
    source_path = mkdir_with_chmod('source')
    this_time = time.time()
    # if source data not ready
    filedate = os.path.getmtime(source_path)
    if this_time - filedate < 20.0:
        return
    # create new path for blank
    new_path = os.path.join(blanks_path, str(uuid.uuid4()))
    print(f"create {new_path}")
    # copy data
    shutil.copytree(source_path, new_path)
    os.chmod(new_path, 0o777)


'''
    Check broken or old blanks
'''


def check_blanks():
    blanks_path = mkdir_with_chmod('blanks')
    source_path = mkdir_with_chmod('source')
    this_time = time.time()
    # if source data not ready
    filedate = os.path.getmtime(source_path)
    if this_time - filedate < 20.0:
        return
    # get ready blanks
    blanks_dirs = get_dirs(blanks_path)
    remove_uuid = None
    with open(os.path.join(source_path, '.uuid'), 'r') as source:
        source_uuid = source.read()
        for blank_dir in blanks_dirs:
            if remove_uuid is not None:
                break
            try:
                with open(os.path.join(blank_dir, '.uuid'), 'r') as f:
                    blank_uuid = f.read()
                    # if uuid update (new source data)
                    if source_uuid != blank_uuid:
                        # if this cold dir
                        filedate = os.path.getmtime(blank_dir)
                        if this_time - filedate > 60.0:
                            remove_uuid = blank_dir
            except Exception as e:
                print(e)
                try:
                    # if this broken blank remove them
                    filedate = os.path.getmtime(blank_dir)
                    # if this cold dir
                    if this_time - filedate > 60.0:
                        remove_uuid = blank_dir
                except Exception as e:
                    print(e)
    if remove_uuid is not None:
        print(f'remove {remove_uuid}')
        shutil.rmtree(remove_uuid)


'''
    Remove not use services by updates in dir
'''


def clean_mounted():
    mounted_path = mkdir_with_chmod('mounted')
    mounted_dirs = get_dirs(mounted_path)
    this_time = time.time()
    uuid = None
    for mounted_dir in mounted_dirs:
        if uuid is not None:
            break
        # if this cold dir very long
        newest = max(glob.glob(os.path.join(mounted_dir, '*')), key=os.path.getmtime)
        filedate = os.path.getmtime(newest)
        if this_time - filedate > 60.0 * 10:
            uuid = os.path.basename(mounted_dir)
    if uuid is not None:
        # remove service!
        call([
            "rancher",
            "rm",
            os.getenv('COMPOSE_PROJECT_NAME') + f'/service-{uuid}'
        ])
        # remove storage!
        call([
            "rancher",
            "volume",
            "rm",
            os.getenv('SERVICE_NFS_VOLUME', f'mounted') + f'/{uuid}'
        ])
        shutil.rmtree(os.path.join(mounted_path, uuid))
        print(f'remove {uuid} not use service')
