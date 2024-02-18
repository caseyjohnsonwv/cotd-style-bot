import json
from fastapi import APIRouter, Response, HTTPException, status as HTTPStatusCode
from pydantic import BaseModel
import db
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
POST '/admin/database/refresh'
Admin route to refresh TOTD in database.
Implicitly disables notifications, but can send them if explicitly instructed.
"""
class DatabaseRefreshBody(AdminBody):
    suppress_notifications:bool | None = True

@router.post('/database/refresh')
def database_refresh(body:DatabaseRefreshBody):
    if body.admin_key != env.ADMIN_KEY:
        raise HTTPException(status_code=HTTPStatusCode.HTTP_401_UNAUTHORIZED, detail='Invalid admin key')
    jobs.refresh_job(suppress_notifications=DatabaseRefreshBody.suppress_notifications)
    print(f"Refreshed data. Notification suppression: {DatabaseRefreshBody.suppress_notifications}")
    return Response(status_code=HTTPStatusCode.HTTP_200_OK)



"""
POST '/admin/database/reset'
Admin route where tables can be truncated (and reloaded, if applicable) manually.
Disallowed in production. This route is for development and debugging only.
"""
@router.post('/database/reset')
def database_reset(body:AdminBody):
    if body.admin_key != env.ADMIN_KEY:
        raise HTTPException(status_code=HTTPStatusCode.HTTP_401_UNAUTHORIZED, detail='Invalid admin key')
    if 'prod' in env.ENV_NAME.strip().lower():
        raise HTTPException(status_code=HTTPStatusCode.HTTP_403_FORBIDDEN, detail='Action is disallowed in production')
    db.drop_all()
    db.do_startup_actions()
    return Response(status_code=HTTPStatusCode.HTTP_200_OK)
