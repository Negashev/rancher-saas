import os
import time
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch import helpers

from store.base import BaseStorage


class ElasticsearchStorage(BaseStorage):
    prefix = os.getenv('PREFIX_STORAGE', 'maas')
    mapping = {
        "settings": {
            "index": {
                "number_of_shards": os.getenv("number_of_shards", "2"),
                "number_of_replicas": os.getenv("number_of_replicas", "2"),
                "store": {
                    "type": "mmapfs"
                }
            }
        }
    }

    def __init__(self, hosts=os.getenv("ES_HOST", None), **kwargs):
        if hosts is None:
            hosts = ['http://es']
        self.driver = Elasticsearch(hosts=hosts, **kwargs)

    def drop_db(self):
        self.driver.indices.delete(f"{self.prefix}-server-dirs")
        self.driver.indices.delete(f"{self.prefix}-delivery-dirs")

    def create_db(self):
        if not self.driver.indices.exists(f"{self.prefix}-server-dirs"):
            res = self.driver.indices.create(index=f"{self.prefix}-server-dirs", ignore=400, body=self.mapping)
            print(res)
        if not self.driver.indices.exists(f"{self.prefix}-delivery-dirs"):
            res = self.driver.indices.create(index=f"{self.prefix}-delivery-dirs", ignore=400, body=self.mapping)
            print(res)

    def cleanup_db(self):
        self_time = int(time.time())
        self.driver.delete_by_query(index=f"{self.prefix}-server-dirs",
                                    body={
                                        "query": {
                                            "bool": {
                                                "must": [
                                                    {
                                                        "match_all": {}
                                                    },
                                                    {
                                                        "range": {
                                                            "uptime": {
                                                                "gte": 0,
                                                                "lt": int(self_time - 30)
                                                            }
                                                        }
                                                    }
                                                ],
                                                "filter": [],
                                                "should": [],
                                                "must_not": []
                                            }
                                        }
                                    })
        self.driver.delete_by_query(index=f"{self.prefix}-delivery-dirs",
                                    body={
                                        "query": {
                                            "bool": {
                                                "must": [
                                                    {
                                                        "match_all": {}
                                                    },
                                                    {
                                                        "range": {
                                                            "uptime": {
                                                                "gte": 0,
                                                                "lt": int(self_time - 86400)
                                                            }
                                                        }
                                                    }
                                                ],
                                                "filter": [],
                                                "should": [],
                                                "must_not": []
                                            }
                                        }
                                    })

    def set_dir(self, directory, hostname, dirType, self_time):
        return helpers.bulk(self.driver,
                            self._yield_set_dirs(f"{self.prefix}-server-dirs", [directory], hostname, dirType,
                                                 self_time),
                            refresh=True)

    def set_dirs(self, directories, hostname, dirType, self_time):
        if not directories:
            return None
        return helpers.bulk(self.driver,
                            self._yield_set_dirs(f"{self.prefix}-server-dirs", directories, hostname, dirType,
                                                 self_time),
                            refresh=True)

    def _yield_set_dirs(self, index, directories, hostname, dirType, self_time):
        timestamp = int(time.mktime(datetime.strptime(self_time, '%Y-%m-%d %H:%M:%S').timetuple()))
        for directory in directories:
            yield {
                "_index": index,
                "_type": "document",
                "_id": directory,
                "_source": {
                    "hostname": hostname,
                    "dirType": dirType,
                    "time": self_time,
                    "timestamp": timestamp
                }
            }

    def delivery_dir(self, uuid):
        self_time = int(time.time())
        try:
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "match_all": {}
                            },
                            {
                                "match_phrase": {
                                    "dirType": {
                                        "query": "blanks"
                                    }
                                }
                            },
                            {
                                "range": {
                                    "timestamp": {
                                        "gte": int(self_time - 10),
                                        "lt": int(self_time + 100)
                                    }
                                }
                            }
                        ],
                        "filter": [],
                        "should": [],
                        "must_not": []
                    }
                }
            }
            data = self.driver.create(
                index=f"{self.prefix}-delivery-dirs",
                doc_type="document",
                id=self.driver.search(
                    index=f"{self.prefix}-server-dirs",
                    filter_path=['hits.hits._id'],
                    body=query,
                    size=1)['hits']['hits'][0]['_id'],
                body={
                    "delivery": uuid, "uptime": int(time.time())
                })
            if data:
                return data['_id']
        except Exception as e:
            print(e)
            return None
        return None

    def get_address(self, uuid):
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_all": {}
                        },
                        {
                            "match_phrase": {
                                "delivery": {
                                    "query": uuid
                                }
                            }
                        }
                    ],
                    "filter": [],
                    "should": [],
                    "must_not": []
                }
            }
        }
        data = self.driver.search(
            index=f"{self.prefix}-delivery-dirs",
            filter_path=['hits.hits._source.address'],
            body=query,
            size=1)
        if data:
            return data['hits']['hits'][0]['_source']['address']
        return None

    def get_uuid_by_address(self, address):
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_all": {}
                        },
                        {
                            "match_phrase": {
                                "address": {
                                    "query": address
                                }
                            }
                        }
                    ],
                    "filter": [],
                    "should": [],
                    "must_not": []
                }
            }
        }
        data = self.driver.search(
            index=f"{self.prefix}-delivery-dirs",
            filter_path=['hits.hits._source.delivery'],
            body=query,
            size=1)
        if data:
            return data['hits']['hits'][0]['_source']['delivery']
        return None

    def get_directory_for_move(self, directories):
        directories_es_array = [{"match_phrase": {"_id": i}} for i in directories]
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_all": {}
                        },
                        {
                            "bool": {
                                "should": directories_es_array,
                                "minimum_should_match": 1
                            }
                        }
                    ],
                    "filter": [],
                    "should": [],
                    "must_not": [
                        {
                            "exists": {
                                "field": "address"
                            }
                        }
                    ]
                }
            }
        }
        data = self.driver.search(
            index=f"{self.prefix}-delivery-dirs",
            filter_path=['hits.hits._id', 'hits.hits._source.delivery'],
            body=query,
            size=1)
        if data:
            return data['hits']['hits'][0]['_id'], data['hits']['hits'][0]['_source']['delivery']
        return None, None

    def set_address_for_directory(self, directory, address):
        return self.driver.update(
            index=f"{self.prefix}-delivery-dirs",
            doc_type="document",
            id=directory,
            body={"doc": {
                "address": address, "uptime": int(time.time())
            }})

    def get_mounted(self, mounted_uuid):
        mounted_uuid_es_array = [{"match_phrase": {"_id": i}} for i in mounted_uuid]
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_all": {}
                        },
                        {
                            "bool": {
                                "should": mounted_uuid_es_array,
                                "minimum_should_match": 1
                            }
                        }
                    ],
                    "filter": [],
                    "should": [],
                    "must_not": []
                }
            }
        }
        data = self.driver.search(
            index=f"{self.prefix}-delivery-dirs",
            filter_path=['hits.hits._id'],
            body=query,
            size=1000)
        if data:
            return [i['_id'] for i in data['hits']['hits']]
        return []

    def get_all_mounted(self):
        return [i for i in helpers.scan(self.driver, index=f"{self.prefix}-delivery-dirs",
                                        doc_type="document")]

    def get_sleep_mounted(self, directories):
        self_time = int(time.time())
        directories_es_array = [{"match_phrase": {"_id": i}} for i in directories]
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_all": {}
                        },
                        {
                            "range": {
                                "uptime": {
                                    "gte": 0,
                                    "lt": int(self_time - 3600)
                                }
                            }
                        },
                        {
                            "bool": {
                                "should": directories_es_array,
                                "minimum_should_match": 1
                            }
                        }
                    ],
                    "filter": [],
                    "should": [],
                    "must_not": []
                }
            }
        }
        data = self.driver.search(
            index=f"{self.prefix}-delivery-dirs",
            filter_path=['hits.hits._id'],
            body=query,
            size=10)
        if data:
            return [i['_id'] for i in data['hits']['hits']]
        return []

    def del_mounted(self, mounted_uuid):
        return self.driver.delete_by_query(index=f"{self.prefix}-deliver-dirs",
                                           body={
                                               "query": {
                                                   "bool": {
                                                       "must": [
                                                           {
                                                               "match_all": {}
                                                           },
                                                           {
                                                               "match_phrase": {
                                                                   "_id": {
                                                                       "query": mounted_uuid
                                                                   }
                                                               }
                                                           }
                                                       ],
                                                       "filter": [],
                                                       "should": [],
                                                       "must_not": []
                                                   }
                                               }
                                           }, ignore_unavailable=True)

    def ping_address(self, address, uptime=int(time.time())):
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_all": {}
                        },
                        {
                            "match_phrase": {
                                "address": {
                                    "query": address
                                }
                            }
                        }
                    ],
                    "filter": [],
                    "should": [],
                    "must_not": []
                }
            }
        }

        return self.driver.update(
            index=f"{self.prefix}-delivery-dirs",
            doc_type="document",
            id=self.driver.search(
                index=f"{self.prefix}-delivery-dirs",
                filter_path=['hits.hits._id'],
                body=query,
                size=1)['hits']['hits'][0]['_id'],
            body={"doc": {
                "uptime": uptime, "address": address
            }})

    def ping_tmp_address(self, address):
        return self.ping_address(address, uptime=int(time.time()) - 3000)
