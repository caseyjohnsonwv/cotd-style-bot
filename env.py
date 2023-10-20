from dotenv import load_dotenv
load_dotenv()

import os
ADMIN_KEY = os.environ['ADMIN_KEY']
DISCORD_APP_ID = os.environ['DISCORD_APP_ID']
DISCORD_BOT_TOKEN = os.environ['DISCORD_BOT_TOKEN']
ENV_NAME = os.environ['ENV_NAME']
NOTIFICATIONS_ENABLED_DEFAULT = bool(os.environ['NOTIFICATIONS_ENABLED_DEFAULT'])
VERIFY_SIGNATURES = bool(os.environ['VERIFY_SIGNATURES'])
