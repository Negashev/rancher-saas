def get_service_uuid(SERVICE_UUID=None, file_path='/tmp/uuid.file'):
    service_uuid = SERVICE_UUID
    if service_uuid is None:
        f = open(file_path, 'r')
        service_uuid = f.read()
    return service_uuid


def set_service_uuid(data, file_path='/tmp/uuid.file'):
    with open(file_path, 'w') as f:
        f.write(data)
    return data
