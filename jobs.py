from datetime import datetime
import json
import re
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import requests
from tinydb import where
from db import maps_table, subs_table
import env



SCHEDULER = BackgroundScheduler(timezone='CET')
CET_TZ = pytz.timezone('CET')

CONTROL_CHARS_PATTERN = '\\$(?:[wnoitsgz]|[0-9A-F]{3})'



"""
NOTIFY JOB
Scheduled job, invoked by the end of REFRESH JOB like a DAG. Sends style notifications to applicable Discord channels.
"""
def notify_job():
    # query maps table
    map_record = maps_table.all()[-1]
    tags_lower = [t.lower() for t in map_record['tags']]
    # query subscriptions table
    subscriptions = subs_table.search(where('style').map(lambda s:s.lower()).one_of(tags_lower))
    print(f"Found {len(subscriptions)} matching subscriptions")
    # build message payloads
    messages = []
    for sub_record in subscriptions:
        payload = {
            'type': 4,
            'content' : f"<@&{sub_record['role_id']}>",
            'embeds' : [
                {
                    'title' : f"It's Cup of the Day time!",
                    'url' : 'https://trackmania.io/#/totd',
                    'fields' : [
                        {
                            'name' : f"{map_record['map_name']} by {map_record['author_name']} (AT: {map_record['author_time']:.3f})",
                            'value' : f"TMX says this map is {' / '.join([t.upper() for t in map_record['tags']])}!",
                        }
                    ],
                    'image' : {
                        'url' : map_record['thumbnail_url'],
                    },
                },
            ]
        }
        subscription_id = sub_record['subscription_id']
        target_url = f"https://discord.com/api/channels/{sub_record['channel_id']}/messages"
        t = (subscription_id, target_url, payload)
        messages.append(t)
    # push to all subscribers
    print(f"Pushing {len(messages)} notifications")
    for sub_id, url, payload in messages:
        body = json.dumps(payload)
        resp = requests.post(url, data=body, headers=env.DISCORD_HEADERS)
        print(f"{sub_id}: {resp.status_code}")



"""
REFRESH JOB
Scheduled job to retrieve the new COTD at 7pm CET / 1pm EST every day.
"""
def refresh_job():
    refresh_timestamp = datetime.utcnow().isoformat()

    # retrieve map from trackmania.io
    url = 'https://trackmania.io/api/totd/0'
    resp = requests.get(url, headers=env.FETCH_HEADERS)
    print(f"trackmania.io: {resp.status_code}")
    tmio_json = resp.json()
    map_uid = tmio_json['days'][-1]['map']['mapUid']
    print(f"totd map_uid: {map_uid}")

    # retrieve same map from tmx
    url = f"https://trackmania.exchange/api/maps/get_map_info/uid/{map_uid}"
    resp = requests.get(url, headers=env.FETCH_HEADERS)
    print(f"tmx: {resp.status_code}")
    tmx_json = resp.json()

    # extract all useful information
    tags = [int(t) for t in tmx_json['Tags'].split(',')]
    tags_readable = [env.TMX_MAP_TAGS[t] for t in tags]
    y,m,d = tmio_json['year'], tmio_json['month'], len(tmio_json['days'])
    map_date = f"{y}-{m}-{d}"
    map_json = tmio_json['days'][-1]['map']
    map_name_cleaned = re.sub(CONTROL_CHARS_PATTERN, '', map_json['name'])
    author_name = map_json['authorplayer']['name']
    author_time = map_json['authorScore'] / 1000
    thumbnail_url = map_json['thumbnailUrl']

    # write to db, which only ever stores one record
    output = {
        'date' : map_date,
        'map_name' : map_name_cleaned,
        'author_name' : author_name,
        'author_time' : author_time,
        'tags' : tags_readable,
        'thumbnail_url' : thumbnail_url,
        'updated' : refresh_timestamp,
    }
    print(f"New map for {map_date} is '{map_name_cleaned}' by {author_name} (AT: {author_time:.3f}) - {tags_readable}")
    maps_table.truncate()
    maps_table.insert(output)
    if env.Settings.notifications_enabled:
        print('Triggering notifications')
        time.sleep(1)
        SCHEDULER.add_job(notify_job, next_run_time=datetime.now(CET_TZ))

# kick off background tasks
SCHEDULER.add_job(refresh_job, CronTrigger.from_crontab('0 19 * * *'), retry_on_exception=True)
SCHEDULER.start()
