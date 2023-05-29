## Installation
You should probably make a virtual environment first. See [the Python venv documentation](https://docs.python.org/3/library/venv.html).

But basically (if you're on Windows) navigate to the root directory of the project and open your terminal, typing:

`python -m venv .venv` to create the virtual environment folder, then

`.\venv\Scripts\activate` to activate the virtual environment.

Then, install the requirements:

`pip install -r requirements.txt`

## Usage

You will need a .env file in the root directory that looks like this:

Example .env file format:

```
DISCORD_TOKEN=oasidjgfoaisjhegoiajseoigjaosiegjoaeijg

LOG_DUMP_CHANNEL_ID=919130617826906112
CHAT_DUMP_CHANNEL_ID=1111128308101431376
STATUS_CHANNEL_ID=851003243755470848
STATUS_MESSAGE_ID=851005967768616980
BOT_ID=851000230441648168
ADMIN_ID=146424676816519168

SERVER_PING_INTERVAL_SECONDS=1

SERVER_IP=localhost
SERVER_PORT=25565
RCON_PORT=25575
RCON_PASSWORD=password
IS_QUERY_ENABLED=True
SERVER_LOGS_FOLDER=/home/samihan/Documents/Minecraft/Summer23/logs/
```

Edit each line to have the appropriate values.

Important things for the `server.properties` file:

```
rcon.port=<insert RCON_PORT value here>
enable-query=true
query.port=<insert SERVER_PORT value here>
server-port=<insert SERVER_PORT value here>
enable-rcon=true
rcon.password=<insert RCON_PASSWORD value here>
```

Edit the `server.properties` file to match.

Lastly, run the program via:

`python bot-server-bridge.py`