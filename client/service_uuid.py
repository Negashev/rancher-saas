import os


def get_service_uuid(file_path='/tmp/uuid.file'):
    if 'SERVICE_UUID' in os.environ:
        service_uuid = os.getenv('SERVICE_UUID')
    else:
        f = open(file_path, 'r')
        service_uuid = f.read()
    return service_uuid


def set_service_uuid(data, file_path='/tmp/uuid.file'):
    if 'SERVICE_UUID' in os.environ:
        data = os.getenv('SERVICE_UUID')
    with open(file_path, 'w') as f:
        f.write(data)
    return data
