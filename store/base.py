import os


class BaseStorage:
    uuid = None
    driver = None
    prefix = 'store'
    schema = os.getenv('STORE_SCHEMA', 'raas')

    def drop_db(self):
        pass

    def create_db(self):
        pass

    def set_dir(self, directory, hostname, dirType, time):
        pass

    def set_dirs(self, directories, hostname, dirType, time):
        pass

    def cleanup_db(self):
        pass

    def update_db(self):
        pass
