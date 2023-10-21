from datetime import datetime
import json
from fastapi import APIRouter, Response, HTTPException, status as HTTPStatusCode
from pydantic import BaseModel
from db import maps_table, subs_table, REDIS, REDIS_KEY
import env
import jobs


router = APIRouter(prefix='/admin')


class AdminBody(BaseModel):
    admin_key: str


"""
GET/PUT '/admin/settings'
Admin route where global settings can be modified.
For example, enable/disable notifications to prevent accidental @Role spam on restart.
"""
class SettingsBody(AdminBody):
    notifications_enabled:bool | None = None

@router.get('/settings')
def get_settings():
    settings = {k:v for k,v in env.Settings.__dict__.items() if not callable(v) and not str(k).startswith('__')}
    return Response(json.dumps(settings), status_code=HTTPStatusCode.HTTP_200_OK)

@router.put('/settings')
def update_settings(body:SettingsBody):
    if body.admin_key != env.ADMIN_KEY:
        raise HTTPException(status_code=HTTPStatusCode.HTTP_401_UNAUTHORIZED, detail='Invalid admin key')
    if body.notifications_enabled:
        env.Settings.notifications_enabled = body.notifications_enabled
    return Response(status_code=HTTPStatusCode.HTTP_200_OK)



"""
GET/POST '/admin/maps'
Admin route where map data can be manually manipulated.
Mostly used for debugging & development.
"""
@router.get('/maps')
def get_maps():
    content = maps_table.all()
    return Response(content=json.dumps(content), status_code=HTTPStatusCode.HTTP_200_OK)

@router.post('/maps')
def refresh_maps(body:AdminBody):
    if body.admin_key != env.ADMIN_KEY:
        raise HTTPException(status_code=HTTPStatusCode.HTTP_401_UNAUTHORIZED, detail='Invalid admin key')
    jobs.SCHEDULER.add_job(jobs.refresh_job, next_run_time=datetime.now(jobs.CET_TZ))
    content = {'message':'Data refresh triggered'}
    return Response(content=json.dumps(content), status_code=HTTPStatusCode.HTTP_202_ACCEPTED)

"""
GET/DELETE '/admin/subscriptions'
Admin route to show or truncate subscriptions. (Note: truncate disallowed in production)
Mostly used for debugging & development.
"""
@router.get('/subscriptions')
def get_subscriptions():
    content = subs_table.all()
    return Response(content=json.dumps(content), status_code=HTTPStatusCode.HTTP_200_OK)

@router.delete('/subscriptions')
def delete_subscriptions(body:AdminBody):
    if body.admin_key != env.ADMIN_KEY:
        raise HTTPException(status_code=HTTPStatusCode.HTTP_401_UNAUTHORIZED, detail='Invalid admin key')
    if 'prod' in env.ENV_NAME.lower():
        raise HTTPException(status_code=HTTPStatusCode.HTTP_405_METHOD_NOT_ALLOWED, detail='DELETE is disallowed in production')
    REDIS.delete(REDIS_KEY)
    with open(REDIS_KEY, 'w') as f:
        json.dump(dict(), f)
    return Response(status_code=HTTPStatusCode.HTTP_204_NO_CONTENT)
