from dotenv import load_dotenv
load_dotenv()

import os
ADMIN_KEY = os.environ['ADMIN_KEY']
DISCORD_APP_ID = os.environ['DISCORD_APP_ID']
DISCORD_BOT_TOKEN = os.environ['DISCORD_BOT_TOKEN']
ENV_NAME = os.environ['ENV_NAME']
NOTIFICATIONS_ENABLED_DEFAULT = True if os.environ['NOTIFICATIONS_ENABLED_DEFAULT'].strip().lower() == 'true' else False
REDIS_HOST = os.environ['REDIS_HOST']
REDIS_PASSWORD = os.environ['REDIS_PASSWORD']
REDIS_PORT = int(os.environ['REDIS_PORT'])
REDIS_USERNAME = os.environ['REDIS_USERNAME']
VERIFY_SIGNATURES = True if os.environ['VERIFY_SIGNATURES'].strip().lower() == 'true' else False


# global map styles from TMX
import json
with open('dat/styles.json', 'r') as f:
    j = dict(json.load(f))
TMX_MAP_TAGS = {int(k):v for k,v in j.items()}


# global headers we'll need for http requests
DISCORD_HEADERS = {'Content-Type':'application/json', 'Authorization':f"Bot {DISCORD_BOT_TOKEN}"}
FETCH_HEADERS = {'User-Agent' : f"kcjwv-icy-cotd-bot-{ENV_NAME}"}

# global app settings that can be updated by the /settings route
class Settings:
    notifications_enabled = NOTIFICATIONS_ENABLED_DEFAULT
