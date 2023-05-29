from disnake.ext.commands import Bot
import observer
from discord_bot import DiscordBotWrapper
from dotenv import load_dotenv
import os
import asyncio
import difflib
import logging
import aiofiles

class BotServerBridge:
    bot_wrapper: DiscordBotWrapper
    discord_token: str
    server: observer.Server
    server_observation_loop_interval_seconds: int
    previous_server_response: observer.ServerResponse | None
    processed_server_logs_file_name: str

    def __init__(self, bot_wrapper: DiscordBotWrapper, discord_token: str, server: observer.Server, server_observation_loop_interval_seconds: int, processed_server_logs_file_name: str) -> None:
        self.bot_wrapper = bot_wrapper
        self.discord_token = discord_token
        self.server = server
        self.server_observation_loop_interval_seconds = server_observation_loop_interval_seconds
        self.previous_server_response = None
        self.processed_server_logs_file_name = processed_server_logs_file_name

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

        def trim_server_info_log(server_log: str) -> str:
            """From a server info log, trims the contents to remove the `[Server thread/INFO]: ` prefix and returns it"""
            log_contents: str = ""
            log_contents = server_log.split("[Server thread/INFO]: ")[1]
            return log_contents

        for log in server_logs:
            if "[Server thread/INFO]:" not in log:
                continue

            # It's hard to intelligently capture all messages
            # It's easier to exclude messages, so we'll do that

            # Trimming log early because it is probably better if there are less characters in each message to linearly scan through
            trimmed_log = trim_server_info_log(log)

            # Excluding certain non-player messages
            if ("<" in trimmed_log and ">" in trimmed_log) is False:
                # [13:13:49] [Server thread/INFO]: PikaGoku lost connection: Disconnected
                if "lost connection" in trimmed_log:
                    continue
                # [13:14:12] [Server thread/INFO]: PikaGoku[/83.221.231.202:1342] logged in with entity id 511 at (-9.837644089959465, 124.0, 100.14206735043899)
                if "logged in with entity id" in trimmed_log:
                    continue
                # [13:22:08] [Server thread/INFO]: There are 1 of a max of 30 players online: PikaGoku
                if "There are" in trimmed_log and "a max of" in trimmed_log and "players online" in trimmed_log:
                    continue
                # [12:54:39] [Server thread/INFO]: [Dynmap] Added 18 custom biome mappings
                if "[Dynmap]" in trimmed_log:
                    continue
                # [12:54:39] [Server thread/INFO]: Starting minecraft server version 1.18.2
                if "Starting minecraft server" in trimmed_log:
                    continue
                # [12:54:39] [Server thread/INFO]: Loading properties
                if "Loading properties" in trimmed_log:
                    continue
                # [12:54:39] [Server thread/INFO]: Default game type: SURVIVAL
                if "Default game type:" in trimmed_log:
                    continue
                # [12:54:39] [Server thread/INFO]: Generating keypair
                if "Generating keypair" in trimmed_log:
                    continue
                # [12:54:39] [Server thread/INFO]: Starting Minecraft server on 51.81.64.4:25565
                if "Starting Minecraft server" in trimmed_log:
                    continue
                # [12:54:39] [Server thread/INFO]: Using epoll channel type
                if "channel type" in trimmed_log:
                    continue
                # [12:54:39] [Server thread/INFO]: Preparing level "fabric_1_18_2_1755343"
                if "Preparing level" in trimmed_log:
                    continue
                # [12:54:48] [Server thread/INFO]: Preparing start region for dimension minecraft:overworld
                if "Preparing start region" in trimmed_log:
                    continue
                # [12:54:57] [Server thread/INFO]: Time elapsed: 8900 ms
                if "Time elapsed:" in trimmed_log:
                    continue
                # [12:54:57] [Server thread/INFO]: Done (17.860s)! For help, type "help"
                if "For help, type" in trimmed_log:
                    continue
                # [12:54:57] [Server thread/INFO]: Starting GS4 status listener
                if "status listener" in trimmed_log:
                    continue
                # [12:54:57] [Server thread/INFO]: Thread Query Listener started
                if "Thread Query Listener" in trimmed_log:
                    continue                        
                # [12:54:57] [Server thread/INFO]: Starting remote control listener
                if "Starting remote control listener" in trimmed_log:
                    continue
                # [12:54:57] [Server thread/INFO]: Thread RCON Listener started
                if "Thread RCON Listener" in trimmed_log:
                    continue
                # [12:54:57] [Server thread/INFO]: RCON running on 51.81.64.4:25575
                if "RCON running on" in trimmed_log:
                    continue
                # [16:48:04] [Server thread/INFO]: Unknown or incomplete command, see below for error
                if "Unknown or incomplete command" in trimmed_log:
                    continue
                # [16:48:04] [Server thread/INFO]: STOP<--[HERE]
                if "[HERE]" in trimmed_log:
                    continue
                # [16:48:06] [Server thread/INFO]: Stopping the server
                if "Stopping the server" in trimmed_log:
                    continue
                # [16:48:07] [Server thread/INFO]: Stopping server
                if "Stopping server" in trimmed_log:
                    continue
                # [16:48:07] [Server thread/INFO]: Saving players
                if "Saving players" in trimmed_log:
                    continue
                # [16:48:07] [Server thread/INFO]: Saving worlds
                if "Saving worlds" in trimmed_log:
                    continue
                # [16:48:08] [Server thread/INFO]: Saving chunks for level 'ServerLevel[world]'/minecraft:overworld
                if "Saving chunks for level" in trimmed_log:
                    continue
                # [16:48:09] [Server thread/INFO]: ThreadedAnvilChunkStorage (world): All chunks are saved
                if "ThreadedAnvilChunkStorage" in trimmed_log:
                    continue
                # [Server thread/INFO]: Made PikaGoku a server operator
                if "a server operator" in trimmed_log:
                    continue
                # [Server thread/INFO]: [PikaGoku: Gave 1 [Acacia Boat] to PikaGoku]
                # [Server thread/INFO]: [PikaGoku: Killed PikaGoku]
                # [Server thread/INFO]: [PikaGoku: Killed PikaGoku]
                # This pattern continues for all operator commands
                if"[" in trimmed_log and ": " in trimmed_log and "]" in trimmed_log:
                    continue

                chat_logs.append(trimmed_log)

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
    
    async def read_processed_server_logs(self) -> list[str]:
        """
        Reads from the file specified by `self.processed_server_logs_file_name` and returns the contents.

        Returns an empty list if the file does not exist.
        """
        processed_server_logs: list[str] = []

        try:
            async with aiofiles.open(self.processed_server_logs_file_name, "r") as processed_server_log_file:
                processed_server_logs = await processed_server_log_file.readlines()
        except FileNotFoundError as exception:
            logging.error(f"Server log file {self.processed_server_logs_file_name} not found! {exception}")
        except Exception as exception:
            logging.error(f"Unhandled exception reading from processed server logs file! {exception}")

        return processed_server_logs

    async def write_processed_server_logs(self, latest_server_logs: list[str]) -> bool:
        """
        Writes the `latest_server_logs` to the file specified by `self.processed_server_logs_file_name`.

        Returns True if the write was successful, False otherwise.
        """
        did_write_successfully = True

        try:
            async with aiofiles.open(self.processed_server_logs_file_name, "w") as processed_server_log_file:
                await processed_server_log_file.writelines(latest_server_logs)
        except Exception as exception:
            logging.error(f"Unhandled exception writing to processed server logs file! {exception}")
            did_write_successfully = False

        return did_write_successfully

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
                # If we have no processed server logs in memory, maybe this script restarted without the server restarting.
                # If that is the case, we don't want to re-send all the logs in latest.log, so we are keeping a record of what we have sent in a file.
                # We are reading from that file here.
                previous_server_logs = await self.read_processed_server_logs()
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

            # Check if the new server response are different to determine if we should update our records for previous server response
            if self.previous_server_response is None or self.previous_server_response.is_equal_to(server_response) is False:
                # Update the previous_server_response in memory
                self.previous_server_response = server_response

                # Write server response to saved.log for persisting a record of what logs we have sent outside of memory.
                did_write_successfully = await self.write_processed_server_logs(server_response.logs_info.server_logs)
                if did_write_successfully is True:
                    logging.debug("Updated processed server logs file successfully.")

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
            logging.info("Received KeyboardInterrupt. Closing bridge...")
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
    processed_server_logs_file_name = f'{os.environ["SERVER_LOGS_FOLDER"]}/saved.log'

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
    
    bridge = BotServerBridge(
        bot_wrapper = bot_wrapper,
        discord_token = discord_token,
        server = server,
        server_observation_loop_interval_seconds=server_observation_loop_interval_seconds,
        processed_server_logs_file_name = processed_server_logs_file_name
    )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(bridge.open_bridge())
    loop.close()
    

if __name__ == "__main__":
    main()