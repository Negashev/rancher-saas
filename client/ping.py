import os
import requests

from apscheduler.schedulers.blocking import BlockingScheduler

from service_uuid import get_service_uuid

SAAS_DELIVERY_TRANSPORT = os.getenv('SAAS_DELIVERY_TRANSPORT', 'http')
SAAS_DELIVERY_URL = os.getenv('SAAS_DELIVERY_URL', '10.100.31.41')
SAAS_DELIVERY_PORT = os.getenv('SAAS_DELIVERY_PORT', 8080)

if 'PING_TMP' in os.environ:
    PING_TYPE = 'tmp'
else:
    PING_TYPE = 'stable'

# Start the scheduler
sched = BlockingScheduler(timezone="UTC")


# Define the function that is to be executed
def ping_job():
    requests.get(f"{SAAS_DELIVERY_TRANSPORT}://{SAAS_DELIVERY_URL}:{SAAS_DELIVERY_PORT}/ping/{PING_TYPE}/{get_service_uuid()}", timeout=4)


# Store the job in a variable in case we want to cancel it
sched.add_job(ping_job, 'interval', seconds=5)

sched.start()
