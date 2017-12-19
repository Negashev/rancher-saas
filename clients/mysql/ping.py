import os
import uuid
from time import sleep

from flask import Flask
from flask_apscheduler import APScheduler
from sqlalchemy.exc import OperationalError

from models import db, Ping, create_mysql_connetion_url


def ping_db():
    with db.app.app_context():
        ping = Ping.query.get(1)
        if ping:
            ping.uuid = str(uuid.uuid4())
            db.session.commit()
        else:
            _uuid = Ping(process=app.config['UUID'], uuid=str(uuid.uuid4()))
            db.session.add(_uuid)
            db.session.commit()


class Config(object):
    SCHEDULER_TIMEZONE = 'UTC'
    JOBS = [
        {
            'id': 'ping_db',
            'func': ping_db,
            'trigger': 'interval',
            'seconds': 30,
            'max_instances': 1
        }
    ]

    SCHEDULER_API_ENABLED = True


if __name__ == '__main__':
    app = Flask(__name__)
    app.config.from_object(Config())
    app.config['SQLALCHEMY_DATABASE_URI'] = create_mysql_connetion_url()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.app = app
    db.init_app(app)
    not_connected = True
    while not_connected:
        try:
            db.create_all()
            not_connected = False
        except OperationalError as e:
            print(f'wait mysql on {mysql_url}')
            sleep(5)

    app.config['UUID'] = str(uuid.uuid4())

    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()

    app.run(
        host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', 80)),
        debug=bool(os.getenv('DEBUG', False))
    )
