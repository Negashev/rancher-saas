import os
import requests
import urllib

from ignite.ignite import IgniteClient, IgniteFailed

from store.base import BaseStorage


class IgniteClientPy3(IgniteClient):

    def make_command(self, cmd, params=None):
        params = {} if params is None else params
        params = urllib.parse.urlencode(
            {k: v for k, v in iter(params.items()) if k and v})
        return requests.get(
            '{endpoint}?cmd={command}&{params}'.format(endpoint=self._endpoint, command=cmd, params=params),
            timeout=int(os.getenv("IGNITE_TIMEOUT", 10))).json()


class IgniteStorage(BaseStorage):
    prefix = 'PUBLIC'

    def __init__(self, host='localhost', port=8080, scheme='http', api_endpoint='ignite'):
        self.driver = IgniteClientPy3(host=host, port=port, scheme=scheme, api_endpoint=api_endpoint)

    def drop_db(self):
        self.driver.qryfldexe(f'''
        DROP TABLE IF EXISTS {self.prefix}.server_dirs
        ''', 1)

    def create_db(self):
        self.driver.qryfldexe(f'''
            CREATE TABLE IF NOT EXISTS {self.prefix}.server_dirs (
        directory VARCHAR PRIMARY KEY,
        hostname VARCHAR,
        dirType VARCHAR,
        time TIMESTAMP
        )
        WITH "template=replicated"
            ''', 1)
        self.driver.qryfldexe(f'''
        CREATE INDEX IF NOT EXISTS htt_idx ON {self.prefix}.server_dirs (dirType, time)
        ''', 1)
        self.driver.qryfldexe(f'''
        CREATE INDEX IF NOT EXISTS dirType_idx ON {self.prefix}.server_dirs (dirType)
        ''', 1)

        self.driver.qryfldexe(f'''
            CREATE TABLE IF NOT EXISTS {self.prefix}.delivery_dirs (
        directory VARCHAR PRIMARY KEY,
        uptime TIMESTAMP,
        deliveryTime TIMESTAMP,
        delivery VARCHAR,
        address VARCHAR        
        )
        WITH "template=replicated"
            ''', 1)
        self.driver.qryfldexe(f'''
        CREATE INDEX IF NOT EXISTS delivery_idx ON {self.prefix}.delivery_dirs (delivery)
        ''', 1)
        self.driver.qryfldexe(f'''
        CREATE INDEX IF NOT EXISTS address_idx ON {self.prefix}.delivery_dirs (address)
        ''', 1)

    def cleanup_db(self):
        self.driver.qryfldexe(f'''
        DELETE FROM {self.prefix}.server_dirs WHERE time < DATEADD('SECOND', -30, NOW())
        ''', 1)

        self.driver.qryfldexe(f'''
        DELETE FROM {self.prefix}.delivery_dirs WHERE uptime < DATEADD('DAY', -1, NOW())
            ''', 1)

    def set_dir(self, directory, hostname, dirType, time):
        return self.driver.qryfldexe(f'''
                MERGE INTO {self.prefix}.server_dirs (directory, hostname, dirType, time) 
                VALUES ('{directory}', '{hostname}', '{dirType}', '{time}')
                ''', 1)

    def set_dirs(self, directories, hostname, dirType, time):
        if not directories:
            return None
        query = f'''
                MERGE INTO {self.prefix}.server_dirs (directory, hostname, dirType, time) 
                VALUES 
                '''
        query += ', '.join([f'''('{directory}', '{hostname}', '{dirType}', '{time}')'''
                            for directory in directories
                            ])
        return self.driver.qryfldexe(query, 1)

    def delivery_dir(self, uuid):
        try:
            self.driver.qryfldexe(f'''
                INSERT INTO {self.prefix}.delivery_dirs (directory, delivery, uptime)
                SELECT directory, '{uuid}' as delivery, NOW() as uptime FROM {self.prefix}.server_dirs
                WHERE dirType='blanks'
                AND time > DATEADD('SECOND', -10, NOW())
                ORDER BY RAND() LIMIT 1
                ''', 1)
        except IgniteFailed as e:
            print(e)
            return None

        data = self.driver.qryfldexe(f'''
            SELECT directory FROM {self.prefix}.delivery_dirs
            WHERE delivery='{uuid}' LIMIT 1
            ''', 1)
        if data['items']:
            return data['items'][0][0]
        return None

    def get_address(self, uuid):
        data = self.driver.qryfldexe(f'''
            SELECT address FROM {self.prefix}.delivery_dirs
            WHERE delivery='{uuid}' LIMIT 1
            ''', 1)
        if data['items']:
            return data['items'][0][0]
        return None

    def get_uuid_by_address(self, address):
        data = self.driver.qryfldexe(f'''
            SELECT delivery FROM {self.prefix}.delivery_dirs
            WHERE address='{address}' LIMIT 1
            ''', 1)
        if data['items']:
            return data['items'][0][0]
        return None

    def get_directory_for_move(self, directories):
        directories_string = "', '".join(directories)
        data = self.driver.qryfldexe(f'''
            SELECT directory, delivery FROM {self.prefix}.delivery_dirs
            WHERE directory in ('{directories_string}')
            AND address is NULL LIMIT 1
            ''', 1)
        if data['items']:
            return data['items'][0]
        return None, None

    def set_address_for_directory(self, directory, address):
        return self.driver.qryfldexe(f'''
            UPDATE {self.prefix}.delivery_dirs
            SET address='{address}'
            WHERE directory = '{directory}'
            ''', 1)

    def get_mounted(self, mounted_uuid):
        directories_string = "', '".join(mounted_uuid)
        data = self.driver.qryfldexe(f'''
            SELECT directory FROM {self.prefix}.delivery_dirs
            WHERE directory in ('{directories_string}')
            ''', 1000)
        if data['items']:
            return [i[0] for i in data['items']]
        return []

    def get_all_mounted(self):
        return self.driver.qryfldexe(f"SELECT directory FROM {self.prefix}.delivery_dirs", 100)['items']

    def get_sleep_mounted(self, directories):
        directories_string = "', '".join(directories)
        data = self.driver.qryfldexe(f'''
            SELECT directory FROM {self.prefix}.delivery_dirs
            WHERE directory in ('{directories_string}')
            AND uptime < DATEADD('HOUR', -1, NOW())
            ''', 10)
        if data['items']:
            return [i[0] for i in data['items']]
        return []

    def del_mounted(self, mounted_uuid):
        return self.driver.qryfldexe(f'''
        DELETE FROM {self.prefix}.delivery_dirs WHERE directory = '{mounted_uuid}'
            ''', 1)

    def ping_address(self, address):
        return self.driver.qryfldexe(f'''
            UPDATE {self.prefix}.delivery_dirs
            SET uptime=NOW()
            WHERE address = '{address}'
            ''', 1)

    def ping_tmp_address(self, address):
        return self.driver.qryfldexe(f'''
            UPDATE {self.prefix}.delivery_dirs
            SET uptime=DATEADD('MINUTE', -50, NOW())
            WHERE address = '{address}'
            ''', 1)
