import json
import time
import requests
from app import DISCORD_HEADERS
import env

def register_commands():
    with open('commands.json', 'r') as f:
        commands_json = json.load(f)
    url = f"https://discord.com/api/applications/{env.DISCORD_APP_ID}/commands"
    for cmd in commands_json:
        resp = requests.post(url, data=json.dumps(cmd), headers=DISCORD_HEADERS)
        print(f"Registering command '/{cmd['name']}': {resp.status_code}")

if __name__ == '__main__':
    register_commands()
    