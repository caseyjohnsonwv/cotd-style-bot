from dotenv import load_dotenv
load_dotenv()

import os
ADMIN_KEY = os.environ['ADMIN_KEY']
DISCORD_APP_ID = os.environ['DISCORD_APP_ID']
DISCORD_BOT_TOKEN = os.environ['DISCORD_BOT_TOKEN']
ENV_NAME = os.environ['ENV_NAME']
NOTIFICATIONS_ENABLED_DEFAULT = bool(os.environ['NOTIFICATIONS_ENABLED_DEFAULT'])
REDIS_HOST = os.environ['REDIS_HOST']
REDIS_PASSWORD = os.environ['REDIS_PASSWORD']
REDIS_PORT = int(os.environ['REDIS_PORT'])
REDIS_USERNAME = os.environ['REDIS_USERNAME']
VERIFY_SIGNATURES = bool(os.environ['VERIFY_SIGNATURES'])
