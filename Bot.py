'''
Created on Jun 6, 2021

@author: ssmup

THIS IS OLD DON'T USE THIS FOR ANYTHING BESIDES REFERENCE
'''

"""
chat improvements DONE

1. keep all commands (from players + server) from showing up in chat
2. keep rando villager death messages from showing up in chat

other improvements

1. add daily back-up feature at 10am

ambitious things

1. track/save player locations?
2. track/save map state
"""

"""
TODO - required by launch day

useful additions to observer

1. can stop server by dm-ing bot
DONE        2. stop DOXXING people
DONE        3. keep full logs in a private chat
DONE        4. keep 'readable' logs in the public chat (where you hide IP) <- regex for IP addresses
"""

#For communicating with Discord API
import discord
#For adding commands to the bot
from discord.ext import commands

#For pinging the server and retrieving information on status, version, and player list
from mcstatus import MinecraftServer

DISCORD_TOKEN = "ODUxMDAwMjMwNDQxNjQ4MTY4.YLx5uQ.c-Y9PMsCE79OTFYlrTSpNiZdp_s"
# (FILTERED_CHAT_)CHANNEL_ID for caves & cliffs part 1 server = 851214332376776784
FULL_LOGS_CHANNEL_ID = 919130617826906112
FILTERED_CHAT_CHANNEL_ID = 918062860414877696

SERVER_STATUS_CHANNEL_ID = 851003243755470848
SERVER_STATUS_MESSAGE_ID = 851005967768616980

SERVER_IP = "70.172.34.123"

#old logs = "/home/samihan/Documents/Minecraft/Caves and Cliffs Server/logs/"
SERVER_LOGS_FOLDER = "/home/samihan/Documents/Minecraft/New Heights Server/logs/"

MCRCON_IP = "192.168.1.16"
MCRCON_PASSWORD = "charg3r"

BOT_NAME = "Observer"
BOT_TAG = "0453"

ADMIN_NAME = "Rudra"
ADMIN_TAG = "8053"

bot = commands.Bot(command_prefix="!observer ", case_insensitive = True)
bot.remove_command("help")

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="I Spy on the Sam's Club server.."))
    print(f"{bot.user.name} has connected to Discord!")
    
    #Start the server bridge
    ping_loop.start()
    
#For issuing tellraw commands to the server to forward Discord messages to in-game
from mcrcon import MCRcon

@bot.event
async def on_message(message):
    if not message.guild:
        if message.author.name == ADMIN_NAME and message.author.discriminator == ADMIN_TAG:
            print("Received command from admin: " + message.content)
            # TODO later - add a check to see if the server is offline and if it is respond to the DM with "Server is offline" so user gets some feedback on their action
            with MCRcon(MCRCON_IP, MCRCON_PASSWORD) as mcr:
                command = '/' + message.content
                response = mcr.command(command)
                # 200 is DM character limit? it says so in the error message when messages are larger than that at least
                if len(response) > 200:
                    response = "Response is too large to send."
                await message.channel.send(response)
    else:
        #print(message)
        author = message.author
        
        #First, make sure the message is not from the bot and in the appropriate channel to send to the server
        #                                                                               author.discriminator != 3158
        if message.channel.id == FILTERED_CHAT_CHANNEL_ID and author.name != BOT_NAME and str(author.discriminator) != BOT_TAG:        
            #If the sender has a nickname, use that but if not use their name (without numbers)
            sender_name = author.name
            if author.nick is not None:
                sender_name = author.nick
                
            #server_message = f"<{name}>: {message.content}"
            
            #print(server_message)
            #command = '/tellraw @a {"text": "' + server_message + '"}'
            
            sender_prefix = f"[{sender_name}] "
            message = message.content
            
            command = '/tellraw @a ["",{"text":"' + sender_prefix + '","color":"aqua"},{"text":"' + message + '"}]'
            
            #print(command)

            with MCRcon(MCRCON_IP, MCRCON_PASSWORD) as mcr:
                response = mcr.command(command)
                #print(response)

from discord.ext import tasks

#Storing information outside of loop so the data persists
last_response = None
player_list = []

@tasks.loop(seconds=1.0)
async def ping_loop():
    """
    Every time it's called, pings the server for information and updates the server status and the server chat log in Discord.
    Chat log updating requires this to be run on the same machine as the server.
    """
    #Stating these are global so the function modifies the global variables
    global last_response
    global player_list
    
    #print("Pinging..")
    
    ping_response = ping_server(SERVER_IP)
    
    if last_response != ping_response:
        #print("Updating server status..")
        
        player_list = ping_response['player_list']
        last_response = ping_response
        
        await update_status_display(ping_response['online'], ping_response['version'], ping_response['player_list'], SERVER_STATUS_CHANNEL_ID, SERVER_STATUS_MESSAGE_ID)
        
    else:
        ''''''
        #print("No updates required to server status")
        
    
    #print("Checking logs..")
    messages_to_display, all_messages = check_logs(SERVER_LOGS_FOLDER + "latest.log", SERVER_LOGS_FOLDER + "stored.log")
    
    if len(messages_to_display) > 0:
        #print("Updating chat channel..")
        await update_log_display(messages_to_display, FILTERED_CHAT_CHANNEL_ID)
    else:
        ''''''
        #print("No messages to display")

    if len(all_messages) > 0:
        #print("Updating logs channel..")
        await update_log_display(all_messages, FULL_LOGS_CHANNEL_ID, all_at_once=True)
    else:
        ''''''
        #print("No messages to display")
    
def ping_server(ip):
    """
    Given an IP, returns whether or not the server is online, how many players are on, and the names of those players.
    """
    
    server = MinecraftServer.lookup(ip)
    
    server_online = False
    server_version = None
    player_list = []
    
    try:
        status = server.status()
        
        server_version = status.version.name
        
        if status.players.online != 0:
            player_list = [player.name for player in status.players.sample]
        
        server_online = True
        #print("Server is online!")
        
    except Exception as error:
        ''''''
        #print(error)
        #print("Server is offline..")
        
    ping_response = {"online": server_online, "version": server_version, "player_list": player_list}
    
    return ping_response

async def update_status_display(online, version, player_list, channel_id, message_id):
    """
    Given a message in a channel, edits that message to display if the server is online, the version it is, and the list of currently online players.
    """
    
    #Get specific ID of channel and message I want the bot to edit with the status information
    display_channel = bot.get_channel(channel_id)
    display_message = await display_channel.fetch_message(message_id)
    
    display_string = "Server Status: **Offline** :no_entry_sign:"
    
    if online:
        display_string = f"Server Status: **Online** :white_check_mark:\n\nVersion: {version}\n\nPlayers Currently Online:\n"
        
        #Turning an empty list into a list with a dummy player so it displays the message via the for loop below
        if len(player_list) == 0:
            player_list = ["Nobody is online..."]
        
        for player in player_list:
            display_string += f"**{player}**"
            display_string += "\n"
    
    await display_message.edit(content = display_string)
    
#For detecting differences in new log files
import difflib

#For copying the changes in the new log file to the old log file
import shutil

#For debug printing
from pprint import pprint

def check_logs(path_to_logs, path_to_old_logs):
    """
    Using a list of already read logs, find any new server log messages via Differ and return them. Also return a pruned/edited list for display in a Discord channel
    """
    
    all_messages = []
    messages_to_display = []
    
    try:
        with open(path_to_logs, 'r') as log_file, open(path_to_old_logs, 'a+') as old_log_file:
            #Returning the the top of the old log file because opening in a+ puts the pointer at the end
            old_log_file.seek(0)
            
            #Use Differ to check which lines exist in log_file but not old_log_file
            differ = difflib.Differ()
            
            #A list of each individual line
            diffed_list = list(differ.compare(log_file.readlines(), old_log_file.readlines()))
            
            # Contains every new log since last log check
            new_logs = []
            # Contains new logs with [Server thread/INFO]: within them
            chat_logs = []
            
            for log in diffed_list:
                #lines unique to the first file (new log file) are preceded with a "- "
                if "-" == log[0]:
                    trimmed_log = log[2:]
                    new_logs.append(trimmed_log)
                    if "[Server thread/INFO]:" in log:
                        chat_logs.append(trimmed_log)

            all_messages = new_logs
                    
            import re

            for message in chat_logs:
            # Including left the game because the player leaves the player list before the logs are processed so 
            # "left the game" messages don't count as having a player name in them
            
                # Censor all IP addresses
                message = re.sub('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', "###.###.###.###", message)

                #Put messages through filters (ONLY LET IN MESSAGES THAT ARE GOOD)
                
                #Log in filter
                if "joined the game" in message:
                    messages_to_display.append(message[32:])
                    continue
                
                #Log out filter
                if "left the game" in message:
                    messages_to_display.append(message[32:])
                    continue
                
                #Chat message filter
                if "<" in message and ">" in message:
                    messages_to_display.append(message[32:])
                    continue
                
                #Death message filter
                
                #From https://minecraft.fandom.com/wiki/Death_messages#Java_Edition
                #Using every specific stub because shortening them to something like "fell" might make player IP log in messages display if the player
                #has "fell" in their name
                #TODO This isn't maintainable - try to find a solution using the death messages stored in server.jar/assets/minecraft/lang/en_us.json
                
                death_message_stubs = [
                    " was shot by",
                    " was pummeled by",
                    " was pricked to death",
                    " walked into a cactus",
                    " drowned",
                    " experienced kinetic energy",
                    " blew up",
                    " was blown up by",
                    " was killed by",
                    " hit the ground too hard",
                    " fell from a high place",
                    " fell off a ladder",
                    " fell off some vines",
                    " fell off some weeping vines",
                    " fell off some twisting vines",
                    " fell off scaffolding",
                    " fell while climbing",
                    "death.fell.accident.water",
                    " was impaled on a stalagmite",
                    " was squashed by",
                    " was skewered by",
                    " went up in flames",
                    " walked into fire",
                    " burned to death",
                    " was burnt to a crisp",
                    " went off with a bang",
                    " tried to swim in lava",
                    " was struck by lightning",
                    " discovered the floor was lava",
                    " walked into danger zone",
                    " was killed by magic",
                    " froze to death",
                    " was frozen to death by",
                    " was slain by",
                    " was fireballed by",
                    " was stung to death",
                    "death.attack.sting.item",
                    " was shot by a skull from",
                    "death.attack.witherSkull.item",
                    " starved to death",
                    " suffocated in a wall",
                    " was squished too much",
                    " was squashed by",
                    " was poked to death by",
                    " was killed trying to hurt",
                    " was impaled by",
                    " fell out of the world",
                    " didn't want to live in the same world as",
                    " withered away",
                    " died from dehydration",
                    " died",
                    " was roasted in dragon breath"
                    ]
                
                if any(death_message in message for death_message in death_message_stubs) and any(player in message for player in player_list):
                    messages_to_display.append(message[32:])
                    continue
                
                #/me message filter
                if any(player in message for player in player_list) and " * " in message:
                    messages_to_display.append(message[32:])
                    continue
                
                #Advancement, Goal, Challenge filter
                if "has made the advancement" in message or "has reached the goal" in message or "has completed the challenge" in message:
                    messages_to_display.append(message[32:])
                    continue
                
                #Server message filter
                if "[Server]" in message:
                    messages_to_display.append(message[32:])
                    continue
            
            #Update old log file
            shutil.copy(path_to_logs, path_to_old_logs)
            
    except Exception as error:
        print(error)
        
    return (messages_to_display, all_messages)
    
async def update_log_display(log_list, channel_id, all_at_once = False):
    """
    Given a list of strings, the bot will print them in the specified channel
    """
    
    #Get specific channel I want the bot to send chat logs to
    display_channel = bot.get_channel(channel_id)
    
    if all_at_once is False:
        for log in log_list:
            if len(log) >= 2000:
                log = "Log too long to send. That's concerning."
            await display_channel.send(log)
        #await display_channel.send("".join(log_list))
    else:
        message = ''.join(log_list)
        if len(message) >= 2000:
            message = "Log too long to send."
        await display_channel.send(message)
        
bot.run(DISCORD_TOKEN)
    
