from contextlib import asynccontextmanager
from datetime import datetime
import json
from fastapi import FastAPI, Response, status as HTTPStatusCode
from db import REDIS, REDIS_KEY, maps_table, subs_table
import admin.router, interaction.router



LAST_RESTART_TIME = datetime.utcnow()



# lifecycle manager to handle startup/shutdown tasks
@asynccontextmanager
async def lifespan(app: FastAPI):

    # startup - load db from redis or local file
    print('Loading DB backup')
    maps = REDIS.get(f"{REDIS_KEY}:maps")
    subs = REDIS.get(f"{REDIS_KEY}:subs")
    if maps:
        maps_table.insert_multiple(json.loads(maps))
        print('Loaded maps successfully')
    if subs:
        subs_table.insert_multiple(json.loads(subs))
        print('Loaded subscriptions successfully')

    # delete data from redis to avoid privacy implications
    # then yield - let application run
    REDIS.delete(f"{REDIS_KEY}:maps")
    REDIS.delete(f"{REDIS_KEY}:subs")
    yield

    # cleanup - export db file back to redis
    print('Exporting DB backup')
    maps = maps_table.all()
    subs = subs_table.all()
    REDIS.set(f"{REDIS_KEY}:maps", json.dumps(maps))
    REDIS.set(f"{REDIS_KEY}:subs", json.dumps(subs))
    print('Exported successfully')
    with open(REDIS_KEY, 'w') as f:
        pass



app = FastAPI(lifespan=lifespan)
app.include_router(admin.router.router)
app.include_router(interaction.router.router)

@app.get('/')
def root():
    now = datetime.utcnow()
    content = {
        'current_time_utc' : now.isoformat(),
        'last_restart_time_utc' : LAST_RESTART_TIME.isoformat(),
        'uptime_seconds' : int((now - LAST_RESTART_TIME).total_seconds()),
    }
    return Response(content=json.dumps(content), status_code=HTTPStatusCode.HTTP_200_OK)
