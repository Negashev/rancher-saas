def get_service_address(SERVICE_ADDR=None, file_path='/tmp/proxy.file'):
    service_address = SERVICE_ADDR
    if service_address is None:
        f = open(file_path, 'r')
        service_address = f.read()
    return service_address
