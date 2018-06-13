import os
import requests
from hashlib import sha1

from apscheduler.schedulers.blocking import BlockingScheduler

from service_uuid import get_service_uuid

# read prefix
f = open('/tmp/prefix.file', 'r')
prefix = f.read()

SAAS_DELIVERY_TRANSPORT = os.getenv(f'{prefix}SAAS_DELIVERY_TRANSPORT', 'http')
SAAS_DELIVERY_URL = os.getenv(f'{prefix}SAAS_DELIVERY_URL', '192.168.122.23')
SAAS_DELIVERY_PORT = os.getenv(f'{prefix}SAAS_DELIVERY_PORT', 8080)

PING_TIME = os.getenv(f'{prefix}PING_TIME', 7200)
if f'{prefix}PING_TMP' in os.environ:
    PING_TIME = 15 * 60

service_sha1 = sha1(get_service_uuid().encode('utf-8')).hexdigest()

url = f"{SAAS_DELIVERY_TRANSPORT}://{SAAS_DELIVERY_URL}:{SAAS_DELIVERY_PORT}/uptime/{service_sha1}/{PING_TIME}"
# Start the scheduler
sched = BlockingScheduler(timezone="UTC")


# Define the function that is to be executed
def ping_job():
    try:
        requests.get(url, timeout=20)
    except Exception as e:
        pass


# Store the job in a variable in case we want to cancel it
sched.add_job(ping_job, 'interval', seconds=5, max_instances=4)

sched.start()
