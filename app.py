from contextlib import asynccontextmanager
from datetime import datetime
import json
from fastapi import FastAPI, Response, status as HTTPStatusCode
from db import REDIS, REDIS_KEY, maps_table, subs_table
import routers.admin, routers.interaction



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

    # yield - let application run
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
app.include_router(routers.admin.router)
app.include_router(routers.interaction.router)

@app.get('/')
def root():
    content = {
        'current_time' : datetime.utcnow().isoformat(),
        'subscriptions_count' : len(subs_table.all()),
    }
    return Response(content=json.dumps(content), status_code=HTTPStatusCode.HTTP_200_OK)
