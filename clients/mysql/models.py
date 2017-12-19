import json
import os
from urllib.parse import urlparse

from flask_sqlalchemy import SQLAlchemy


def create_mysql_connetion_url(file_path='/tmp/envoy.conf'):
    if 'MYSQL_ADDR' in os.environ:
        mysql_url = os.getenv('MYSQL_ADDR')
    else:
        envoy_source = json.load(open(file_path))
        url_parse = urlparse(envoy_source['cluster_manager']['clusters'][0]['hosts'][0]['url'])
        mysql_url = url_parse.netloc
    return f"mysql+pymysql://{os.getenv('MYSQL_USER', 'root')}:{os.getenv('MYSQL_PASSWORD', '')}@{mysql_url}/{os.getenv('MYSQL_DATABASE', '')}"


db = SQLAlchemy()


class Ping(db.Model):
    __tablename__ = os.getenv('MYSQL_PING_TABLE', '__ping')
    id = db.Column(db.Integer, primary_key=True)
    process = db.Column(db.String(36))
    uuid = db.Column(db.String(36))
    date = db.Column(db.DateTime, default=db.func.current_timestamp())
