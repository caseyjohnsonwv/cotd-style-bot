import json
from fastapi import APIRouter, Response, HTTPException, status as HTTPStatusCode
from pydantic import BaseModel
import db
import env


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
POST '/admin/reset'
Admin route for restting database during development / debugging.
Disallowed in production.
"""
class ResetBody(AdminBody):
    pass

@router.post('/reset')
def reset(body:ResetBody):
    if body.admin_key != env.ADMIN_KEY:
        raise HTTPException(status_code=HTTPStatusCode.HTTP_401_UNAUTHORIZED, detail='Invalid admin key')
    if 'prod' in env.ENV_NAME.lower():
        raise HTTPException(status_code=HTTPStatusCode.HTTP_403_FORBIDDEN, detail='This function is disallowed in production')
    db.drop_all()
    db.create_all()
    return Response(status_code=HTTPStatusCode.HTTP_200_OK)
