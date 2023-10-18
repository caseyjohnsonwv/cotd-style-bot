# standard libs
from datetime import datetime
import json
import re
import uuid
# third party libs
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi import status as HTTPStatusCode
from pydantic import BaseModel
import requests
from tinydb import TinyDB, where
# custom code
import env
import ref


DISCORD_HEADERS = {'Content-Type':'application/json', 'Authorization':f"Bot {env.DISCORD_BOT_TOKEN}"}
FETCH_HEADERS = {'User-Agent' : f"kcjwv-icy-cotd-bot-{env.ENV_NAME}"}
CONTROL_CHARS_PATTERN = '\\$(?:[wnoitsgz]|[0-9A-F]{3})'



app = FastAPI()
scheduler = BackgroundScheduler(timezone='CET')
db = TinyDB(f"./bot_db.{env.ENV_NAME}.json")
maps_table = db.table('maps')
subs_table = db.table('subscriptions')



"""
GET '/'
Simple healthcheck endpoint.
"""
@app.get('/')
def root():
    return {'current_time' : datetime.now().isoformat()}



"""
POST '/enable'
Turn on notification messages in a specific channel for a specific style.

Parameters:
*guild_id[int]: Discord server ID where message will be posted
*channel_id[int]: Discord channel ID where message will be posted
*style[str]: TMX map style name for which notifications will be pushed
role_id[int]: Optional Discord role ID for tagging a role in the notification

Response: 201 if successfully created
"""
class EnableBody(BaseModel):
    guild_id: int
    channel_id: int
    role_id: int | None = None
    style: str

@app.post('/enable')
def enable(body:EnableBody):
    j = {
        'subscription_id' : str(uuid.uuid4()),
        'guild_id' : body.guild_id,
        'channel_id' : body.channel_id,
        'role_id' : body.role_id,
        'style' : body.style.lower(),
    }
    print(f"/enable: {j}")
    # enforce uniqueness for combination guild_id + style
    subs_table.remove((where('guild_id') == j['guild_id']) & (where('style') == j['style']))
    subs_table.insert(j)
    return Response(status_code=HTTPStatusCode.HTTP_201_CREATED)



"""
POST '/disable'
Turn off notification messages for a specific style.

Parameters:
*guild_id[int]: Discord server ID where message will be posted
*style[str]: TMX map style name for which notifications will be pushed

Response: 200 if found and deleted, 404 if not found
"""
class DisableBody(BaseModel):
    guild_id: int
    style: str

# discord webhooks are always POST, even if DELETE makes more sense
@app.post('/disable')
def disable(body:DisableBody):
    j = {
        'guild_id' : body.guild_id,
        'style' : body.style.lower(),
    }
    print(f"/disable: {j}")
    removed = subs_table.remove((where('guild_id') == j['guild_id']) & (where('style') == j['style']))
    if len(removed) == 0:
        raise HTTPException(status_code=HTTPStatusCode.HTTP_404_NOT_FOUND, detail='Notification config not found')
    return Response(status_code=HTTPStatusCode.HTTP_200_OK)



"""
GET '/styles'
Lists all subscribable map styles from TMX.

Parameters: None
Response: JSONArray of string map style names
"""
# discord webhooks are always POST, even if GET makes more sense
@app.post('/styles')
def get_styles():
    results = list(ref.TMX_MAP_TAGS.values())
    results.sort()
    output = json.dumps(results)
    return Response(content = output, status_code=HTTPStatusCode.HTTP_200_OK)



"""
NOTIFY JOB
Scheduled job, invoked by the end of REFRESH JOB like a DAG. Sends style notifications to applicable Discord channels.
"""
def notify_job():
    # query maps table
    today = datetime.strftime(datetime.today(), '%Y-%m-%d')
    map_record = maps_table.get(where('date') == today)
    tags_lower = [t.lower() for t in map_record['tags']]
    # query subscriptions table
    subscriptions = subs_table.search(where('style').map(lambda s:s.lower()).one_of(tags_lower))
    # build message payloads
    messages = []
    for sub_record in subscriptions:
        message = f"{sub_record['style'].upper()} COTD: \"{map_record['map_name']}\" by {map_record['author_name']} (AT: {map_record['author_time']})"
        subscription_id = sub_record['subscription_id']
        role_id = sub_record.get('role_id')
        if role_id:
            message = f"<@&{role_id}>\n" + message
        target_url = f"https://discord.com/api/channels/{sub_record['channel_id']}/messages"
        t = (subscription_id, target_url, message)
        messages.append(t)
    # push to all subscribers
    for sub_id, url, msg in messages:
        body = json.dumps({'content' : msg})
        resp = requests.post(url, data=body, headers=DISCORD_HEADERS)
        print(f"{sub_id}: {resp.status_code}")

notify_job_obj = scheduler.add_job(notify_job, next_run_time=None) # not scheduled - to be invoked by data ingestion's completion



"""
REFRESH JOB
Scheduled job to retrieve the new COTD at 7pm CET / 1pm EST every day.
"""
def refresh_job():
    refresh_timestamp = datetime.utcnow().isoformat()

    # retrieve map from trackmania.io
    url = 'https://trackmania.io/api/totd/0'
    resp = requests.get(url, headers=FETCH_HEADERS)
    print(f"trackmania.io: {resp.status_code}")
    tmio_json = resp.json()
    map_uid = tmio_json['days'][-1]['map']['mapUid']
    print(f"totd map_uid: {map_uid}")

    # retrieve same map from tmx
    url = f"https://trackmania.exchange/api/maps/get_map_info/uid/{map_uid}"
    resp = requests.get(url, headers=FETCH_HEADERS)
    print(f"tmx: {resp.status_code}")
    tmx_json = resp.json()

    # extract all useful information
    tags = [int(t) for t in tmx_json['Tags'].split(',')]
    tags_readable = [ref.TMX_MAP_TAGS[t] for t in tags]
    y,m,d = tmio_json['year'], tmio_json['month'], len(tmio_json['days'])
    map_date = f"{y}-{m}-{d}"
    map_json = tmio_json['days'][-1]['map']
    map_name_cleaned = re.sub(CONTROL_CHARS_PATTERN, '', map_json['name'])
    author_name = map_json['authorplayer']['name']
    author_time = map_json['authorScore'] / 1000

    # write to db, enforcing uniqueness by date
    output = {
        'date' : map_date,
        'map_name' : map_name_cleaned,
        'author_name' : author_name,
        'author_time' : author_time, 
        'tags' : tags_readable,
        'updated' : refresh_timestamp,
    }
    print(output)
    maps_table.remove(where('date') == output['date'])
    maps_table.insert(output)
    print('Triggering notifications')
    notify_job_obj.modify(next_run_time = datetime.now())

scheduler.add_job(refresh_job, CronTrigger.from_crontab('0 19 * * *'), retry_on_exception=True)



# kick off background tasks
scheduler.start()
