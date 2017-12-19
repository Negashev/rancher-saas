import os
import json
import uuid
from time import sleep

import requests
from flask import Flask
from sqlalchemy.exc import OperationalError

from models import db, Ping, create_mysql_connetion_url

delivery_service = True

app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
if os.path.isfile('/tmp/envoy.conf'):
    print("found proxy config, try connect to service")
    app.config['SQLALCHEMY_DATABASE_URI'] = create_mysql_connetion_url()
    try:
        with app.app_context():
            db.init_app(app)
            ping = Ping.query.get(1)
            if ping:
                delivery_service = False
    except OperationalError as e:
        print(e)

envoy_source = json.load(open('/src/envoy.conf'))

while delivery_service:
    r = requests.get(os.getenv('SAAS_DELIVERY_URL'), timeout=300)
    if r.status_code == 200:
        print(r.text)
        # save conf for envoy to /tmp/envoy.confk
        envoy_source['cluster_manager']['clusters'][0]['hosts'][0][
            'url'] = f"{os.getenv('SAAS_PROTOCOL', 'tcp://')}{r.text}"
        with open('/tmp/envoy.conf', 'w') as f:
            json.dump(envoy_source, f)
        break
    else:
        print(f"{r.status_code} - {r.text}")
        sleep(5)
inserted = False
app.config['SQLALCHEMY_DATABASE_URI'] = create_mysql_connetion_url()
for i in range(1200):
    try:
        with app.app_context():
            db.init_app(app)
            db.create_all()
            _uuid = Ping(process=str(uuid.uuid4()))
            db.session.add(_uuid)
            db.session.commit()
            inserted = True
            break
    except OperationalError as e:
        print('Waiting mysql open port')
    sleep(5)
if not inserted:
    exit('Database not delivery please restart this service')
