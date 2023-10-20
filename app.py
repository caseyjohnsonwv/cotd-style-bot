# standard libs
from datetime import datetime
import json
import re
import time
import uuid
# third party libs
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi import status as HTTPStatusCode
from pydantic import BaseModel
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
import requests
from tinydb import TinyDB, where
# custom code
import env
import ref



DISCORD_PUBLIC_KEY = '59a9c5881d2c0f19456a150b2d9b2b8b203e568164614a2815f7e505c62faa50'
DISCORD_VERIFIER = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))

DISCORD_HEADERS = {'Content-Type':'application/json', 'Authorization':f"Bot {env.DISCORD_BOT_TOKEN}"}
FETCH_HEADERS = {'User-Agent' : f"kcjwv-icy-cotd-bot-{env.ENV_NAME}"}
CONTROL_CHARS_PATTERN = '\\$(?:[wnoitsgz]|[0-9A-F]{3})'



app = FastAPI()
scheduler = BackgroundScheduler(timezone='CET')
db = TinyDB(f"./bot_db.{env.ENV_NAME}.json")
maps_table = db.table('maps')
subs_table = db.table('subscriptions')



# global app settings that can be updated by the /settings route
class Settings:
    notifications_enabled = False



"""
GET '/'
Simple healthcheck endpoint.
"""
@app.get('/')
def root():
    return {'current_time' : datetime.now().isoformat()}



"""
GET/PUT '/settings'
Admin route where global settings can be modified.
For example, enable/disable notifications to prevent accidental @Role spam on restart.
"""
@app.get('/settings')
def get_settings():
    settings = {k:v for k,v in Settings.__dict__.items() if not callable(v) and not str(k).startswith('__')}
    return Response(json.dumps(settings), status_code=HTTPStatusCode.HTTP_200_OK)

class SettingsBody(BaseModel):
    admin_key: str
    notifications_enabled:bool | None = None

@app.put('/settings')
def update_settings(body:SettingsBody):
    if body.admin_key != env.ADMIN_KEY:
        raise HTTPException(status_code=HTTPStatusCode.HTTP_401_UNAUTHORIZED, detail='Invalid admin key')
    if body.notifications_enabled:
        Settings.notifications_enabled = body.notifications_enabled
    return Response(status_code=HTTPStatusCode.HTTP_200_OK)



"""
POST '/interaction'
Endpoint where Discord interactions will be sent.
https://discord.com/developers/docs/interactions/receiving-and-responding#receiving-an-interaction
"""
class Commands:
    DISABLE = 'disable'
    ENABLE = 'enable'
    HELP = 'help'
    STYLES = 'styles'

@app.post('/interaction')
async def interaction(req:Request):
    raw_body = await req.body()
    body = raw_body.decode('utf-8')
    signature = req.headers.get('X-Signature-Ed25519')
    timestamp = req.headers.get('X-Signature-Timestamp')
    if env.VERIFY_SIGNATURES:
        try:
            DISCORD_VERIFIER.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        except BadSignatureError:
            raise HTTPException(status_code=HTTPStatusCode.HTTP_401_UNAUTHORIZED, detail='Invalid request signature')
    # respond to discord's security tests
    j = await req.json()
    if j['type'] == 1:
        content = json.dumps({'type':1})
        return Response(content=content, status_code=HTTPStatusCode.HTTP_200_OK)
    # handle slash commands
    elif j['type'] == 4:
        guild_id = j['guild_id']
        channel_id = j['channel_id']
    return Response(content=json.dumps({'message':'Check app logs'}), status_code=HTTPStatusCode.HTTP_200_OK)



"""
CRUD util for putting a notification config in the database
Returns: UUID of created notification
"""
def enable(guild_id:int, channel_id:int, role_id:int, style:str) -> str:
    subscription_id = str(uuid.uuid4())
    j = {
        'subscription_id' : subscription_id,
        'guild_id' : guild_id,
        'channel_id' : channel_id,
        'role_id' : role_id,
        'style' : style.lower(),
    }
    # enforce uniqueness for combination guild_id + style
    subs_table.remove((where('guild_id') == j['guild_id']) & (where('style') == j['style']))
    subs_table.insert(j)
    return subscription_id



"""
CRUD util for removing a notification from the database
Returns: number of configs deleted (may be 0, 1, or greater than 1)
"""
def disable(guild_id:int, style:str) -> int:
    j = {
        'guild_id' : guild_id,
        'style' : style.lower(),
    }
    removed = subs_table.remove((where('guild_id') == j['guild_id']) & (where('style') == j['style']))
    return len(removed)


# """
# GET '/styles'
# Lists all subscribable map styles from TMX.

# Parameters: None
# Response: JSONArray of string map style names
# """
# # discord webhooks are always POST, even if GET makes more sense
# @app.post('/styles')
# def get_styles():
#     results = list(ref.TMX_MAP_TAGS.values())
#     results.sort()
#     output = json.dumps(results)
#     return Response(content = output, status_code=HTTPStatusCode.HTTP_200_OK)



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
    if Settings.notifications_enabled:
        print('Triggering notifications')
        notify_job_obj.modify(next_run_time = datetime.now())
    else:
        print('Notifications disabled - done')

scheduler.add_job(refresh_job, CronTrigger.from_crontab('0 19 * * *'), retry_on_exception=True)



"""
REGISTER_COMMANDS JOB
One-time task on startup to register slash commands with Discord developer portal
"""
def register_commands_job():
    with open('commands.json', 'r') as f:
        commands_json = json.load(f)
    url = f"https://discord.com/api/applications/{env.DISCORD_APP_ID}/commands"
    for cmd in commands_json:
        resp = requests.post(url, data=json.dumps(cmd), headers=DISCORD_HEADERS)
        print(f"Registering command '/{cmd['name']}': {resp.status_code}")
        time.sleep(1)
    print('Done')

# scheduler.add_job(register_commands_job) # runs automatically on startup



# kick off background tasks
scheduler.start()
