from datetime import datetime
import json
import re
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import requests
import db
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
    payloads = db.get_notification_payloads()
    print(f"Found {len(payloads)} matching subscriptions")
    # build message payloads
    messages = []
    for notif in payloads:
        payload = {
            'type': 4,
            'content' : f"<@&{notif.role_id}>",
            'embeds' : [
                {
                    'title' : f"It's Cup of the Day time!",
                    'url' : 'https://trackmania.io/#/totd',
                    'fields' : [
                        {
                            'name' : f"{notif.track_name} by {notif.author} (AT: {notif.author_time:.3f})",
                            'value' : f"TMX says this map is {' / '.join([t.upper() for t in notif.track_tags])}!",
                        }
                    ],
                    'image' : {
                        'url' : notif.thumbnail_url,
                    },
                },
            ]
        }
        target_url = f"https://discord.com/api/channels/{notif.channel_id}/messages"
        t = (notif.channel_id, target_url, payload)
        messages.append(t)
    # push to all subscribers
    print(f"Pushing {len(messages)} notifications")
    for channel_id, url, payload in messages:
        body = json.dumps(payload)
        resp = requests.post(url, data=body, headers=env.DISCORD_HEADERS)
        print(f"{channel_id}: {resp.status_code}")



"""
REFRESH JOB
Scheduled job to retrieve the new COTD at 7pm CET / 1pm EST every day.
"""
def refresh_job(suppress_notifications:bool=False):
    # retrieve map from trackmania.io
    url = 'https://trackmania.io/api/totd/0'
    resp = requests.get(url, headers=env.FETCH_HEADERS)
    print(f"trackmania.io: {resp.status_code}")
    tmio_json = resp.json()
    map_uid = tmio_json['days'][-2]['map']['mapUid']
    print(f"totd map_uid: {map_uid}")

    # retrieve same map from tmx
    url = f"https://trackmania.exchange/api/maps/get_map_info/uid/{map_uid}"
    resp = requests.get(url, headers=env.FETCH_HEADERS)
    print(f"tmx: {resp.status_code}")
    try:
        tmx_json = resp.json()
    except requests.exceptions.JSONDecodeError as ex:
        print(ex)
        print('This error usually means the map has not been uploaded to TMX')
        return

    # extract all useful information
    tags = [int(t) for t in tmx_json['Tags'].split(',')]
    y,m,d = tmio_json['year'], tmio_json['month'], len(tmio_json['days'])
    map_date = datetime(y,m,d)
    map_json = tmio_json['days'][-1]['map']
    map_name_cleaned = re.sub(CONTROL_CHARS_PATTERN, '', map_json['name'])
    author_name = map_json['authorplayer']['name']
    author_time = map_json['authorScore'] / 1000
    thumbnail_url = map_json['thumbnailUrl']

    # write to db
    db.create_track(
        uid=map_uid,
        date=map_date,
        name=map_name_cleaned,
        author=author_name,
        author_time=author_time,
        thumbnail_url=thumbnail_url,
    )
    db.create_track_tags_reference(
        track_uid=map_uid,
        track_tags=tags
    )
    print(f"New map for {map_date.isoformat()} is '{map_name_cleaned}' by {author_name} (AT: {author_time:.3f}) - {tags}")
    if env.Settings.notifications_enabled and not suppress_notifications:
        print('Triggering notifications')
        time.sleep(1)
        SCHEDULER.add_job(notify_job, next_run_time=datetime.now(CET_TZ))

# kick off background tasks
SCHEDULER.add_job(refresh_job, CronTrigger.from_crontab('0 19 * * *', timezone=CET_TZ), retry_on_exception=True)
SCHEDULER.start()
