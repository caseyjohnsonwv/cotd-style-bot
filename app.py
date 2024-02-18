from contextlib import asynccontextmanager
from datetime import datetime
import json
from fastapi import FastAPI, Response, status as HTTPStatusCode
import db
import admin.router, interaction.router



LAST_RESTART_TIME = datetime.utcnow()



# lifecycle manager to handle startup/shutdown tasks
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup - create db tables if not exist
    db.drop_all()
    db.create_all()
    db.populate_style_table()
    # yield to let application run
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(admin.router.router)
app.include_router(interaction.router.router)

@app.get('/')
def root():
    now = datetime.utcnow()
    content = {
        'current_time_utc' : now.isoformat(),
        'last_restart_time_utc' : LAST_RESTART_TIME.isoformat(),
        'uptime_seconds' : (now - LAST_RESTART_TIME).total_seconds() // 1,
        'uptime_days' : (now - LAST_RESTART_TIME).total_seconds() / 86400,
    }
    return Response(content=json.dumps(content), status_code=HTTPStatusCode.HTTP_200_OK)
