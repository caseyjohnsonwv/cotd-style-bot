import json
import uuid
from fastapi import APIRouter, Request, Response, HTTPException, status as HTTPStatusCode
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from tinydb import where
from db import subs_table
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
    def show():
        pass
    

    SUBSCRIBE = 'subscribe'
    def subscribe(guild_id:int, channel_id:int, role_id:int, style:str) -> str:
        subscription_id = str(uuid.uuid4())
        j = {
            'subscription_id' : subscription_id,
            'guild_id' : guild_id,
            'channel_id' : channel_id,
            'role_id' : role_id,
            'style' : style.lower(),
        }
        # enforce uniqueness for combination guild_id + style
        subs_table.remove((where('guild_id') == j['guild_id']) & (where('style') == j['style']))
        subs_table.insert(j)
        return subscription_id


    STYLES = 'styles'
    def styles():
        results = list(env.TMX_MAP_TAGS.values())
        results.sort()
        return results
    

    UNSUBSCRIBE = 'unsubscribe'
    def unsubscribe(guild_id:int, style:str) -> int:
        j = {
            'guild_id' : guild_id,
            'style' : style.lower(),
        }
        removed = subs_table.remove((where('guild_id') == j['guild_id']) & (where('style') == j['style']))
        return len(removed)



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
        subscriptions = Command.show()
        message = "Your command worked, but it hasn't been implemented yet"
    
    elif command == Command.SUBSCRIBE:
        role_id, style = options.get('role'), options.get('style')
        # enforce role & style requirement
        if not role_id or not style:
            raise HTTPException(status_code=HTTPStatusCode.HTTP_422_UNPROCESSABLE_ENTITY, detail='Role and Style are required')
        # enforce style validity
        style = style.strip().lower()
        if style not in [s.lower() for s in env.TMX_MAP_TAGS.values()]:
            fields = [
                {'name' : 'Failure!', 'value' : f'"{style.upper()}" is not a valid map style! Use /styles to see all available options.'}
            ]
        # any additional error scenarios would go here
        else:
            subscription_id = Command.subscribe(guild_id, channel_id, role_id, style)
            print(f"Created subscription {subscription_id} for server {guild_id}")
            fields = [
                {'name' : 'Success!', 'value' : f"You are now subscribed to {style.upper()}! I will mention <@&{role_id}> here in <#{channel_id}> when this style becomes Cup of the Day."},
                {'name' : 'Reminder:', 'value' : f"If you have previously configured another role or channel for this style, the previous configuration has been overwritten."}
            ]

    elif command == Command.STYLES:
        styles_list = Command.styles()
        styles_fmt = '\n'.join([f"{i+1}. {s}" for i,s in enumerate(styles_list)])
        message = f"All of the following are valid style names:\n{styles_fmt}"

    elif command == Command.UNSUBSCRIBE:
        style = options.get('style')
        if not style:
            raise HTTPException(status_code=HTTPStatusCode.HTTP_422_UNPROCESSABLE_ENTITY, detail='Style is required')
        num_removed = Command.unsubscribe(guild_id, style)
        print(f"Removed {num_removed} subscriptions for server {guild_id}")
        if num_removed == 0:
            message = f"Subscription not found for {style.upper()} - nothing to delete!"
        else:
            message = f"Unsubscribed from {style.upper()}!"

    # preserve legacy functionality while building embeds
    if len(fields) > 0:
        content['data']['embeds'][0]['fields'] = fields
    else:
        content['data']['content'] = message
        del content['data']['embeds']
    print(content)

    # format into json and return
    return Response(content=json.dumps(content), status_code=HTTPStatusCode.HTTP_200_OK, media_type='application/json')
