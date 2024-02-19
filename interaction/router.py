import itertools
import json
from typing import List
from fastapi import APIRouter, Request, Response, HTTPException, status as HTTPStatusCode
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
import db
import env



DISCORD_PUBLIC_KEY = '59a9c5881d2c0f19456a150b2d9b2b8b203e568164614a2815f7e505c62faa50'
DISCORD_VERIFIER = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))



router = APIRouter()



"""
POST '/interaction'
Endpoint where Discord interactions will be sent.
https://discord.com/developers/docs/interactions/receiving-and-responding#receiving-an-interaction
"""
class InteractionType:
    PING = 1
    CHAT = 4

class Command:
    HELP = 'help'
    def help():
        pass


    SHOW = 'show'
    def show(guild_id:int) -> List[dict]:
        results = db.get_subscriptions_for_guild(guild_id)
        return [{'channel_id':r.channel_id, 'role_id':r.role_id, 'style_name':r.style_name} for r in results]
    

    SUBSCRIBE = 'subscribe'
    def subscribe(guild_id:int, channel_id:int, role_id:int, style_name:str) -> int:
        subscription_id = db.create_subscription(
            guild_id=guild_id,
            channel_id=channel_id,
            role_id=role_id,
            style_name=style_name
        )
        return subscription_id


    STYLES = 'styles'
    def styles():
        return db.get_all_style_names()
    

    UNSUBSCRIBE = 'unsubscribe'
    def unsubscribe(guild_id:int, style_name:str=None, role_id:int=None) -> bool:
        if not style_name and not role_id:
            raise Exception('At minimum, one of Style or Role is required')
        return db.delete_subscription(guild_id=guild_id, style_name=style_name, role_id=role_id)



@router.post('/interaction')
async def interaction(req:Request):
    raw_body = await req.body()
    body = raw_body.decode()
    signature = req.headers.get('X-Signature-Ed25519')
    timestamp = req.headers.get('X-Signature-Timestamp')

    # respond to discord's security tests
    if env.VERIFY_SIGNATURES:
        try:
            DISCORD_VERIFIER.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        except BadSignatureError:
            raise HTTPException(status_code=HTTPStatusCode.HTTP_401_UNAUTHORIZED, detail='Invalid request signature')
    j = await req.json()
    if j['type'] == InteractionType.PING:
        content = {'type':InteractionType.PING}
        return Response(content=json.dumps(content), status_code=HTTPStatusCode.HTTP_200_OK, media_type='application/json')

    # handle slash commands
    content = {
        'type' : InteractionType.CHAT,
        'data' : {'embeds' : [{'fields' : []}]},
        'allowed_mentions' : [] # suppress @ mentions so we can still pretty print the roles & channels
    }
    fields = []

    print(j)
    guild_id = j['guild_id']
    channel_id = j['channel_id']
    command = j['data']['name']
    options = {}
    if j['data'].get('options'):
        for option in j['data']['options']:
            name, value = option['name'], option['value']
            options[name] = value


    if command == Command.HELP:
        help_text = Command.help()
        message = "Your command worked, but it hasn't been implemented yet"


    elif command == Command.SHOW:
        result = Command.show(guild_id=guild_id)
        if len(result) == 0:
            fields = [{'name' : 'Failure!', 'value' : "No subscriptions found for this server."}]
        else:
            subscription_strings = [f"{n+1}. {r['style_name'].upper()} -> <#{r['channel_id']}> (<@&{r['role_id']}>)" for n,r in enumerate(result)]
            fields = [{'name' : f"Found {len(subscription_strings)} Subscription(s):", 'value' : '\n'.join(subscription_strings)}]
    

    elif command == Command.SUBSCRIBE:
        role_id, style_name = options.get('role'), options.get('style')
        # enforce role & style requirement
        if not role_id or not style_name:
            raise HTTPException(status_code=HTTPStatusCode.HTTP_422_UNPROCESSABLE_ENTITY, detail='Role and Style are required')
        # any additional error scenarios would go here
        else:
            subscription_id = Command.subscribe(guild_id=guild_id, channel_id=channel_id, role_id=role_id, style_name=style_name)
            print(f"Created subscription {subscription_id} for server {guild_id}")
            fields = [
                {'name' : 'Success!', 'value' : f"You are now subscribed to {style_name.upper()}! I will mention <@&{role_id}> here in <#{channel_id}> when this style becomes Cup of the Day."},
                {'name' : 'Reminder:', 'value' : f"If you have previously configured another role or channel for this style, the previous configuration has been overwritten."}
            ]


    elif command == Command.STYLES:
        fields = [
            {'name': 'Valid map styles according to TMX:', 'value': '(These are case insensitive.)'}
        ]
        styles_list = Command.styles()
        styles_fmt = [f"{i+1}. {s}" for i,s in enumerate(styles_list)]
        # split into columns for condensed tabular display
        for col in itertools.batched(styles_fmt, sum(divmod(len(styles_fmt), 3))):
            fields.append({'name':'', 'value': '\n'.join(col), 'inline':True})


    elif command == Command.UNSUBSCRIBE:
        style_name = options.get('style')
        role_id = options.get('role')
        if not style_name and not role_id:
            raise HTTPException(status_code=HTTPStatusCode.HTTP_422_UNPROCESSABLE_ENTITY, detail='Style and/or Role is required')
        # other error handling goes here if needed
        else:
            is_removed = Command.unsubscribe(guild_id=guild_id, style_name=style_name, role_id=role_id)
            msg = style_name or f"<@&{role_id}>"
            msg = msg.upper()
            if is_removed:
                fields = [
                    {'name' : 'Success!', 'value' : f"Unsubscribed from {msg} notifications."},
                ]
            else:
                fields = [
                    {'name' : 'Failure!', 'value' : f"Subscription not found for {msg} - nothing to delete."},
                ]


    # preserve legacy functionality while building embeds
    if len(fields) > 0:
        content['data']['embeds'][0]['fields'] = fields
    else:
        content['data']['content'] = message
        del content['data']['embeds']
    print(content)
    

    # format into json and return
    return Response(content=json.dumps(content), status_code=HTTPStatusCode.HTTP_200_OK, media_type='application/json')
