"""
TODO:
Test if all_players stores values correctly, if new_chat_logs is populated with the correct information, and if that information is printed

other improvements

1. add daily back-up feature at 10am (apex host does this already though so maybe no need)

ambitious things

1. track/save player locations?
2. track/save map state
"""

# For obtaining platform information for debug printing
import platform, os
# For communicating with Discord API and implementing a Bot
import disnake
# For scheduling commands to loop
from disnake.ext import tasks
from disnake.ext.commands import Bot
# For pinging the server and retrieving information on status, version, and player list
from mcstatus import JavaServer
# For running commands on the server
from mcrcon import MCRcon
# For using FTP to access server logs remotely
from ftplib import FTP
# For detecting differences in new log files
import difflib
# For censoring IP addresses from logs
import re
# For type hinting
from typing import Tuple

# TODO: Put all of these final values in a config file or something

DISCORD_TOKEN = "ODUxMDAwMjMwNDQxNjQ4MTY4.YLx5uQ.c-Y9PMsCE79OTFYlrTSpNiZdp_s"
# TODO: Replace these with the new channel IDs for every new server iteration
LOG_DUMP_CHANNEL_ID = 919130617826906112 # Testing channel: 969147675058503730
CHAT_DUMP_CHANNEL_ID = 978637209160785950 # Testing channel: 969147630707937280
STATUS_CHANNEL_ID, STATUS_MESSAGE_ID = 851003243755470848, 851005967768616980 # Testing values: -1, -1

SAVED_LOGS_PATH = "saved.log"

# TODO: Replace this with whatever IP is necessary
SERVER_IP = "localhost" #"70.172.34.123"

# TODO: Replace this with whatever login is necessary
# FTP_ADDRESS = "1569.node.apexhosting.gdn"
# FTP_USER = "PikaGoku.1348505"
# FTP_PASSWORD = "U65.cjK47G#exU"

SERVER_LOGS_FOLDER = "/home/samihan/Documents/Minecraft/Newer Heights Server/logs/"

# TODO: Replace these with actual values
MCRCON_IP = SERVER_IP
MCRCON_PASSWORD = "interc3pt"

BOT_NAME = "Observer"
BOT_TAG = "0453"

# TODO: If I want the bot to be able to be used by multiple people for multiple servers, this should be able to be different for different servers
ADMIN_NAME = "Rudra"
ADMIN_TAG = "8053"

# TODO: Maybe change this from default intents to only the one that lets it post/edit messages
bot = Bot(command_prefix="!observer ", intents=disnake.Intents.default())
bot.remove_command("help")

@bot.event
async def on_ready() -> None:
    """
    The code in this even is executed when the bot is ready
    """
    print(f"Logged in as {bot.user.name}")
    print(f"disnake API version: {disnake.__version__}")
    print(f"Python version: {platform.python_version()}")
    print(f"Running on: {platform.system()} {platform.release()} ({os.name})")
    print("-------------------")
    # Start the server bridge
    ping_loop.start()

# Handle messages
@bot.event
async def on_message(message: disnake.Message):
    # If it's a DM, check if it's an admin command
    if not message.guild:
        if message.author.name == ADMIN_NAME and message.author.discriminator == ADMIN_TAG:
            print("Received command from admin: " + message.content)
            # TODO later - add a check to see if the server is offline and if it is respond to the DM with "Server is offline" so user gets some feedback on their action
            try:
                with MCRcon(MCRCON_IP, MCRCON_PASSWORD) as mcr:
                    command = '/' + message.content
                    response = mcr.command(command)
                    # 200 is DM character limit? it says so in the error message when messages are larger than that at least
                    while len(response) > 200:
                        try:
                            await message.channel.send(response[:200])
                        except Exception as exception:
                            print(exception)
                        response = response[200:]
                    try:
                        await message.channel.send(response)
                    except Exception as exception:
                        print(exception)
            except Exception as error:
                try:
                    await message.channel.send("Error occurred while connecting to the server via MCRcon. Cannot execute admin command.")
                    await message.channel.send(error)
                except Exception as exception:
                    print(exception)
                print("Error occurred while connecting to the server via MCRcon. Cannot execute admin command.")
        else:
            # This DM is not from admin, don't do anything
            pass
        return
           
    # First, make sure the message is not from the bot and in the appropriate channel to send to the server
    if message.channel.id == CHAT_DUMP_CHANNEL_ID and message.author.name != BOT_NAME and str(message.author.discriminator) != BOT_TAG:      
        
        sender_name = message.author.name
        
        # Old, not doing this anymore because using the senders normal Discord name keeps things more sensical as it will be consistently one name
        '''
        # If the sender has a nickname, use that but if not use their name (without numbers)
        if message.author.nick is not None:
            sender_name = message.author.nick
        '''

        # TODO: I'm not sure what happens if the Discord message is really long. Is there a limit to how long the command can be for RCON? Figure that out at some point.
        
        command = '/tellraw @a ["",{"text":"' + f"[{sender_name}] " + '","color":"aqua"},{"text":"' + message.content + '"}]'

        try:
            with MCRcon(MCRCON_IP, MCRCON_PASSWORD) as mcr:
                response = mcr.command(command)
        except Exception as error:
            print("Error trying to RCON to server. Cannot display Discord message in Minecraft chat")
            print(error)
            pass

#Storing information outside of loop so the data persists
last_response = None
# List of players currently online
player_list = []
# List of all players who have connected in current bot session
# Including [Server] is to include /say commands from console and also to have some dummy value for edge case log detection
all_players = ["[Server]"]

@tasks.loop(seconds=1.0)
async def ping_loop():
    """
    Every time it's called, pings the server for information and updates the server status and the server chat log in Discord.
    Chat log updating requires this to be run on the same machine as the server.
    """
    # Stating these are global so the function modifies the global variables
    global last_response
    global player_list

    # Ping server for current information
    is_server_online = False
    server_version = None
    current_player_list = []

    try:
        server = JavaServer.lookup(SERVER_IP)
        status = server.status()
        server_version = status.version.name
        if status.players.sample is not None:
            current_player_list = [player.name for player in status.players.sample]
        player_list = current_player_list
        is_server_online = True
        # print("Server is online!")
    except Exception as error:
        # print(error)
        # print("Server is offline..")
        pass

    ping_response = (is_server_online, server_version, current_player_list)

    # print(ping_response)
    
    if last_response != ping_response:
        # print("Updating server status..")
        
        player_list = current_player_list
        all_players.extend([player for player in player_list if player not in all_players])

        last_response = ping_response
        
        await update_status_display(is_server_online, server_version, player_list, STATUS_CHANNEL_ID, STATUS_MESSAGE_ID)
        
    else:
        # print("No updates required to server status")
        pass
    
    #print("Checking logs..")
    new_chat_logs, all_new_logs = update_logs()
    
    if len(new_chat_logs) > 0:
        print("Updating chat channel..")
        await update_log_display(new_chat_logs, CHAT_DUMP_CHANNEL_ID)

    if len(all_new_logs) > 0:
        print("Updating logs channel..")
        await update_log_display(all_new_logs, LOG_DUMP_CHANNEL_ID, all_at_once=True)

async def update_status_display(is_online: bool, version: str, player_list: list[str], channel_id: int, message_id: int) -> None:
    """
    Given a message in a channel, edits that message to display if the server is online, the version it is, and the list of currently online players.
    """
    
    try:
        # Get specific ID of channel and message I want the bot to edit with the status information
        display_channel = bot.get_channel(channel_id)
        display_message = await display_channel.fetch_message(message_id)
    except Exception as error:
        print(error)
        print("Error fetching status display channel/message; cannot update it")
        return
    
    display_string = "Server Status: **Offline** :no_entry_sign:"
    
    if is_online:
        display_string = f"Server Status: **Online** :white_check_mark:\n\nVersion: {version}\n\nPlayers Currently Online:\n"
        
        #Turning an empty list into a list with a dummy player so it displays the message via the for loop below
        if len(player_list) == 0:
            player_list = ["Nobody is online..."]
        
        for player in player_list:
            display_string += f"**{player}**\n"
    
    await display_message.edit(content = display_string)

def update_logs() -> Tuple[str, str]:
    """
    Fetch latest logs from the server, then return (new_chat_logs, all_new_logs) where 
    new_chat_logs are messages to display in a chat log and all_new_logs are all new logs since last fetch
    """

    try:
        # A list of each individual line
        all_new_logs:list[str] = []
        # Contains new logs with [Server thread/INFO]: within them
        new_chat_logs:list[str] = []

        latest_logs:list[str] = []
        saved_logs:list[str] = []

        # with FTP(SERVER_IP) as ftp:
        #     ftp.login(user=FTP_USER, passwd=FTP_PASSWORD)
        #     # TODO: This command/path probably needs to change if I use a different server host
        #     ftp.retrlines("RETR /default/logs/latest.log", latest_logs.append)

        LATEST_LOG_FILE = SERVER_LOGS_FOLDER + "/latest.log"

        with open(LATEST_LOG_FILE, "r") as file:
            latest_logs = file.readlines()

        with open(SAVED_LOGS_PATH, 'a+') as saved_logs_file:
            # Returning the the top of the old log file because opening in a+ puts the pointer at the end
            saved_logs_file.seek(0)
            saved_logs = saved_logs_file.readlines()
        
        # Strip newline character from the end of every line in saved_logs
        # saved_logs = [log.rstrip("\n") for log in saved_logs]

        # Use Differ to check which lines in latest_logs are new
        differ = difflib.Differ()
        diffs = differ.compare(latest_logs, saved_logs)

        # Debug stuff
        """
        for diff in diffs:
            print(repr(diff))
        input()
        """

        for line in diffs:
            # Lines unique to the new logs are preceded with a "- "
            if line[0] == "-":
                # Drop the "- " before saving the lines to lists
                line = line[2:]
                all_new_logs.append(line)

        for message in [log for log in all_new_logs if "[Server thread/INFO]:" in log]:
            # Censor all IP addresses
            message = re.sub('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', "###.###.###.###", message)

            for player in all_players:
                # Debug stuff
                """
                print(message)
                if len(message) > 32:
                    print(message[32:])
                """
                
                if player in message and (message[32:].startswith(player) or message[32:].startswith(f" {player}") or message[32:].startswith(f" <{player}>") or message[32:].startswith(f" * {player}")):
                    # Add exceptions as necessary
                    # Exception 1: messages like '[08:20:33] [Server thread/INFO]: PikaGoku[/###.###.###.###:60959] logged in with entity id 4526 at (8.634433988285775, 106.0, 99.4292995068352)'
                    if (message[32:].startswith(f" {player}[/")):
                        continue
                    print(f"{player} is in {message}")
                    new_chat_logs.append(message[32:])
                    break
                # This is to include new players' 'joined the game' messages
                elif message.endswith("joined the game"):
                    new_chat_logs.append(message[32:])
                    break
            
        # Save new logs
        with open(SAVED_LOGS_PATH, 'w') as saved_logs_file:
            saved_logs_file.write("".join(latest_logs))

    except Exception as error:
        print("Error in the process of analyzing which logs are new")
        print(error)
        return ([], ["Error in the process of analyzing which logs are new"])
        pass
        
    return (new_chat_logs, all_new_logs)

async def update_log_display(log_list: list[str], channel_id: int, all_at_once: bool = False) -> None:
    """
    Given a list of strings, the bot will print them in the specified channel
    """
    
    # Get specific channel I want the bot to send chat logs to
    display_channel = bot.get_channel(channel_id)
    
    if all_at_once is False:
        for log in log_list:
            while len(log) >= 2000:
                try:
                    await display_channel.send(log[:2000])
                except Exception as exception:
                    print(exception)
                log = log[2000:]
            try:
                await display_channel.send(log)
            except Exception as exception:
                print(exception)
    else:
        message = '\n'.join(log_list)
        while len(message) >= 2000:
            try:
                await display_channel.send(message[:2000])
            except Exception as exception:
                print(exception)
            message = message[2000:]
        try:
            await display_channel.send(message)
        except Exception as exception:
            print(exception)

bot.run(DISCORD_TOKEN)
