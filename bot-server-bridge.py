from disnake.ext.commands import Bot
import observer
from discord_bot import DiscordBotWrapper
from dotenv import load_dotenv
import os
import asyncio
import difflib
import logging

class BotServerBridge:
    bot_wrapper: DiscordBotWrapper
    discord_token: str
    server: observer.Server
    server_observation_loop_interval_seconds: int
    previous_server_response: observer.ServerResponse | None

    def __init__(self, bot_wrapper: DiscordBotWrapper, discord_token: str, server: observer.Server, server_observation_loop_interval_seconds: int) -> None:
        self.bot_wrapper = bot_wrapper
        self.discord_token = discord_token
        self.server = server
        self.server_observation_loop_interval_seconds = server_observation_loop_interval_seconds
        self.previous_server_response = None

    @staticmethod
    def extract_new_logs(current_logs: list[str], previous_logs: list[str]) -> list[str]:
        """
        Uses difflib to determine which logs are new to the `current_logs` and returns them.
        """
        differ = difflib.Differ()
        log_delta = differ.compare(current_logs, previous_logs)

        # If a line is unique to `current_logs` (the latest log information), it will start with `"- "``
        # Also, remove that "- " while we're iterating over everything anyway
        new_logs: list[str] = [delta[2:].rstrip("\n") for delta in log_delta if delta.startswith("- ")]

        return new_logs
    
    @staticmethod
    def extract_chat_logs(server_logs: list[str]) -> list[str]:
        """
        From a set of `server_logs`, extract which logs are chat logs and return them.

        Also, processes the chat logs if necessary.
        """
        chat_logs: list[str] = []

        for log in server_logs:
            if "[Server thread/INFO]:" not in log:
                continue

            # It's hard to intelligently capture all messages
            # It's easier to exclude messages, so we'll do that

            # Excluding certain non-player messages
            if ("<" in log and ">" in log) is False:
                # [13:13:49] [Server thread/INFO]: PikaGoku lost connection: Disconnected
                if "lost connection" in log:
                    continue
                # [13:14:12] [Server thread/INFO]: PikaGoku[/83.221.231.202:1342] logged in with entity id 511 at (-9.837644089959465, 124.0, 100.14206735043899)
                if "logged in with entity id" in log:
                    continue
                # [13:22:08] [Server thread/INFO]: There are 1 of a max of 30 players online: PikaGoku
                if "There are" in log and "a max of" in log and "players online" in log:
                    continue
                # [12:54:39] [Server thread/INFO]: [Dynmap] Added 18 custom biome mappings
                if "[Dynmap]" in log:
                    continue
                # [12:54:39] [Server thread/INFO]: Starting minecraft server version 1.18.2
                if "Starting minecraft server" in log:
                    continue
                # [12:54:39] [Server thread/INFO]: Loading properties
                if "Loading properties" in log:
                    continue
                # [12:54:39] [Server thread/INFO]: Default game type: SURVIVAL
                if "Default game type:" in log:
                    continue
                # [12:54:39] [Server thread/INFO]: Generating keypair
                if "Generating keypair" in log:
                    continue
                # [12:54:39] [Server thread/INFO]: Starting Minecraft server on 51.81.64.4:25565
                if "Starting Minecraft server" in log:
                    continue
                # [12:54:39] [Server thread/INFO]: Using epoll channel type
                if "channel type" in log:
                    continue
                # [12:54:39] [Server thread/INFO]: Preparing level "fabric_1_18_2_1755343"
                if "Preparing level" in log:
                    continue
                # [12:54:48] [Server thread/INFO]: Preparing start region for dimension minecraft:overworld
                if "Preparing start region" in log:
                    continue
                # [12:54:57] [Server thread/INFO]: Time elapsed: 8900 ms
                if "Time elapsed:" in log:
                    continue
                # [12:54:57] [Server thread/INFO]: Done (17.860s)! For help, type "help"
                if "For help, type" in log:
                    continue
                # [12:54:57] [Server thread/INFO]: Starting GS4 status listener
                if "status listener" in log:
                    continue
                # [12:54:57] [Server thread/INFO]: Thread Query Listener started
                if "Thread Query Listener" in log:
                    continue                        
                # [12:54:57] [Server thread/INFO]: Starting remote control listener
                if "Starting remote control listener" in log:
                    continue
                # [12:54:57] [Server thread/INFO]: Thread RCON Listener started
                if "Thread RCON Listener" in log:
                    continue
                # [12:54:57] [Server thread/INFO]: RCON running on 51.81.64.4:25575
                if "RCON running on" in log:
                    continue
                # [16:48:04] [Server thread/INFO]: Unknown or incomplete command, see below for error
                if "Unknown or incomplete command" in log:
                    continue
                # [16:48:04] [Server thread/INFO]: STOP<--[HERE]
                if "[HERE]" in log:
                    continue
                # [16:48:06] [Server thread/INFO]: Stopping the server
                if "Stopping the server" in log:
                    continue
                # [16:48:07] [Server thread/INFO]: Stopping server
                if "Stopping server" in log:
                    continue
                # [16:48:07] [Server thread/INFO]: Saving players
                if "Saving players" in log:
                    continue
                # [16:48:07] [Server thread/INFO]: Saving worlds
                if "Saving worlds" in log:
                    continue
                # [16:48:08] [Server thread/INFO]: Saving chunks for level 'ServerLevel[world]'/minecraft:overworld
                if "Saving chunks for level" in log:
                    continue
                # [16:48:09] [Server thread/INFO]: ThreadedAnvilChunkStorage (world): All chunks are saved
                if "ThreadedAnvilChunkStorage" in log:
                    continue

                def extract_chat_message(server_log: str) -> str:
                    """From a server log, trims the contents to only be the chat message and returns it"""
                    chat_message: str = ""
                    chat_message = server_log.split("[Server thread/INFO]: ")[1]
                    return chat_message

                chat_message = extract_chat_message(log)
                chat_logs.append(chat_message)

        return chat_logs
        

    async def optionally_update_status_display(self, status_info: observer.ServerStatusResponse) -> bool | None:
        """
        Determine if the provided `status_info` is different from the most recently observed `status_info`, and if so, 
        make a call to update the status display, returning the value returned by that function call.

        If not, don't do that, and return None.
        """
        if self.previous_server_response is not None and status_info.is_equal_to(self.previous_server_response.status_info) == True:
            return None

        update_response = await self.bot_wrapper.update_status_display(status_info)

        return update_response
    
    async def optionally_update_server_log_display(self, new_server_logs: list[str]) -> bool | None:
        """
        If the `new_server_logs` list isn't empty, make a call to update the server logs display, returning the value returned by that function call.

        If not, don't do that, and return None.
        """
        if len(new_server_logs) == 0:
            return None
        
        update_response = await self.bot_wrapper.update_server_log_display(new_server_logs)

        return update_response
    
    async def optionally_update_chat_log_display(self, new_chat_logs: list[str]) -> bool | None:
        """
        If the `new_chat_logs` list isn't empty, make a call to update the chat logs display, returning the value returned by that function call.

        If not, don't do that, and return None.
        """
        if len(new_chat_logs) == 0:
            return None
        
        update_response = await self.bot_wrapper.update_chat_log_display(new_chat_logs)

        return update_response

    async def server_observation_loop(self) -> None:
        """
        With a delay of `self.server_observation_loop_interval_seconds` between iterations, get server information and if any changes have happened, tell the bot to update channels.
        """
        while True:
            # Ping the server
            server_response = await self.server.ping_server()

            # Get required information from the server response
            previous_server_logs = []
            if self.previous_server_response is None:
                # TODO: Read the previous server logs from the saved.log file
                pass
            elif self.previous_server_response is not None:
                previous_server_logs = self.previous_server_response.logs_info.server_logs

            new_server_logs = self.extract_new_logs(server_response.logs_info.server_logs, previous_server_logs)
            new_chat_logs = self.extract_chat_logs(new_server_logs)

            _, status_response, server_logs_response, chat_logs_response = await asyncio.gather(
                asyncio.sleep(self.server_observation_loop_interval_seconds),
                self.optionally_update_status_display(server_response.status_info),
                self.optionally_update_server_log_display(new_server_logs),
                self.optionally_update_chat_log_display(new_chat_logs)
            )

            if status_response is True:
                logging.debug("Updated status display successfully.")

            if server_logs_response is True:
                logging.debug("Updated server logs display successfully.")
        
            if chat_logs_response is True:
                logging.debug("Updated chat logs display successfully.")

            self.previous_server_response = server_response

            #TODO: Write server response to saved.log

        return

    async def open_bridge(self) -> None:
        """
        Add the discord bot and the server observation loop to the active event loop and run until interrupted by KeyboardInterrupt.

        This is "starting" everything.
        """

        start_bot_task = asyncio.create_task(self.bot_wrapper.discord_bot.start(self.discord_token))
        start_observation_loop_task = asyncio.create_task(self.server_observation_loop())

        try:
            await asyncio.gather(start_bot_task, start_observation_loop_task)
        except KeyboardInterrupt:
            pass
        return

def main():
    logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)

    load_dotenv(".env")

    logging.info("Loaded .env file.")
    logging.debug(os.environ)

    server_ip = os.environ["SERVER_IP"]
    port = int(os.environ["SERVER_PORT"])
    rcon_port = int(os.environ["RCON_PORT"])
    rcon_password = os.environ["RCON_PASSWORD"]
    is_query_enabled = (os.environ["IS_QUERY_ENABLED"].lower() == "true")
    server_log_file_name = f'{os.environ["SERVER_LOGS_FOLDER"]}/latest.log'

    server = observer.Server(
        ip = server_ip,
        port = port,
        rcon_port = rcon_port,
        rcon_password = rcon_password,
        is_query_enabled = is_query_enabled,
        server_log_file_name = server_log_file_name,
    )

    status_message_channel_id = int(os.environ["STATUS_CHANNEL_ID"])
    status_message_message_id = int(os.environ["STATUS_MESSAGE_ID"])
    logs_dump_channel_id = int(os.environ["LOG_DUMP_CHANNEL_ID"])
    chat_dump_channel_id = int(os.environ["CHAT_DUMP_CHANNEL_ID"])
    discord_token = os.environ["DISCORD_TOKEN"]
    bot_id = int(os.environ["BOT_ID"])
    admin_id = int(os.environ["ADMIN_ID"])

    bot_wrapper = DiscordBotWrapper(
        status_message_channel_id = status_message_channel_id,
        status_message_message_id = status_message_message_id,
        logs_dump_channel_id = logs_dump_channel_id,
        chat_dump_channel_id = chat_dump_channel_id,
        bot_id = bot_id,
        admin_id = admin_id,
        send_chat_message_callback=server.send_chat_message,
        run_console_command_callback=server.run_console_command
    )

    server_observation_loop_interval_seconds = int(os.environ["SERVER_PING_INTERVAL_SECONDS"])
    
    bridge = BotServerBridge(bot_wrapper = bot_wrapper, discord_token = discord_token, server = server, server_observation_loop_interval_seconds=server_observation_loop_interval_seconds)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(bridge.open_bridge())
    loop.close()
    

if __name__ == "__main__":
    main()