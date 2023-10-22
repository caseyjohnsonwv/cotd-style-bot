import redis
from tinydb import TinyDB
import env

REDIS = redis.Redis(host=env.REDIS_HOST, port=env.REDIS_PORT, username=env.REDIS_USERNAME, password=env.REDIS_PASSWORD, decode_responses=True)
REDIS_KEY = f"bot.{env.ENV_NAME}.db"

db = TinyDB(REDIS_KEY)
maps_table = db.table('maps')
subs_table = db.table('subscriptions')
