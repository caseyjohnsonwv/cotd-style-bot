from nacl.signing import VerifyKey
import env


DISCORD_PUBLIC_KEY = '59a9c5881d2c0f19456a150b2d9b2b8b203e568164614a2815f7e505c62faa50'
DISCORD_VERIFIER = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
DISCORD_HEADERS = {'Content-Type':'application/json', 'Authorization':f"Bot {env.DISCORD_BOT_TOKEN}"}

FETCH_HEADERS = {'User-Agent' : f"kcjwv-icy-cotd-bot-{env.ENV_NAME}"}



# global app settings that can be updated by the /settings route
class Settings:
    notifications_enabled = env.NOTIFICATIONS_ENABLED_DEFAULT
