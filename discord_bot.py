import disnake
from disnake.ext.commands import Bot
from disnake.channel import TextChannel
from disnake.message import Message
import platform
import os
import observer
import logging
import asyncio
import typing

bot = Bot(command_prefix="!observer ", intents=disnake.Intents.default())
bot.remove_command("help")

@bot.event
async def on_ready() -> None:
    """
    The code in this event is executed when the bot is ready
    """
    print(f"Logged in as {bot.user.name}")
    print(f"disnake API version: {disnake.__version__}")
    print(f"Python version: {platform.python_version()}")
    print(f"Running on: {platform.system()} {platform.release()} ({os.name})")
    print("-------------------")

class DiscordBotWrapper:
    discord_bot: Bot
    status_message_channel_id: int
    status_message_message_id: int
    logs_dump_channel_id: int
    chat_dump_channel_id: int
    bot_id: int
    admin_id: int
    # send_chat_message_callback: typing.Callable[[str, str], typing.Awaitable[bool]]
    send_chat_message_callback: typing.Callable[[str, str], typing.Awaitable[bool]]
    run_console_command_callback: typing.Callable[[str], typing.Awaitable[bool]]

    def __init__(
            self, status_message_channel_id: int,
            status_message_message_id: int,
            logs_dump_channel_id: int,
            chat_dump_channel_id: int,
            bot_id: int,
            admin_id: int,
            send_chat_message_callback: typing.Callable[[str, str], typing.Awaitable[bool]],
            run_console_command_callback: typing.Callable[[str], typing.Awaitable[bool]]
        ) -> None:
        """
        Initializing the DiscordBotWrapper object.

        :param int status_message_channel_id: The ID of the channel in which the status message to be updated exists.
        :param int status_message_message_id: The ID of the status message itself.
        :param int logs_dump_channel_id: The ID of the channel in which all server logs should be dumped.
        :param int chat_dump_channel_id: The ID of the channel in which chat logs should be dumped (and messages from this channel will be sent to the server).
        :param int bot_id: The ID of the Discord user of the bot itself.
        :param int admin_id: The ID of the Discord user who should be able to DM the bot and have those DMs work as server commands sent straight to the server console.

        """
        self.discord_bot = bot

        self.status_message_channel_id = status_message_channel_id
        self.status_message_message_id = status_message_message_id
        self.logs_dump_channel_id = logs_dump_channel_id
        self.chat_dump_channel_id = chat_dump_channel_id
        self.bot_id = bot_id
        self.admin_id = admin_id

        self.send_chat_message_callback = send_chat_message_callback
        self.run_console_command_callback = run_console_command_callback

        # Handle messages
        @bot.event
        async def on_message(message: disnake.Message) -> None:
            if message.guild is None and message.author.id == self.admin_id:
                # Run message as a command
                message_send_response = await self.run_console_command_callback(message.content)
                
                # NOTE: Maybe do something with the response here
                return
            
            if message.channel.id == self.chat_dump_channel_id and message.author.id != self.bot_id:
                # Send message to server
                message_send_response = await self.send_chat_message_callback(message.author.name, message.content)

                # NOTE: Maybe do something with the response here?
                return

            return

    async def update_status_display(self, status_information: observer.ServerStatusResponse) -> bool:
        """Use information from the provided `status_information` to craft a message and edit the message specified by `self.status_message_message_id`."""
        did_update_successfully = False

        try:
            # Try loading message from cache first
            status_message = self.discord_bot.get_message(self.status_message_message_id)
            # If message was not in cache, load it 
            if status_message is None:
                logging.debug("Status message not found in bot cache.")
                channel = self.discord_bot.get_channel(self.status_message_channel_id)
                assert type(channel) == TextChannel, "The status message channel ID should be the ID of a text channel."
                status_message = await channel.fetch_message(self.status_message_message_id)
            else:
                logging.debug("Status message successfully loaded from bot cache!")
            new_message_content = ""
            server_status_content = f"Server Status: {'Online :white_check_mark:' if status_information.is_online is True else 'Offline :no_entry_sign:'}\n"
            new_message_content += server_status_content

            if status_information.is_online == True:
                version_content = f"Version: {status_information.version}\n"
                new_message_content += version_content
                player_list_content = ""
                if status_information.online_player_count == 0:
                    player_list_content = "Nobody is online...\n"
                else:
                    player_list_content = "\n".join([f'**{player_name}**' for player_name in status_information.online_player_names])
                new_message_content += player_list_content

            new_message = await status_message.edit(new_message_content)
            # did_update_successfully = (new_message.content == new_message_content) # Not doing this because maybe Discord edits a message slightly (Markup or something) and that's shouldn't be considered a failure to update the message
            did_update_successfully = True
        except Exception as exception:
            logging.error(f"Unhandled exception when trying to update status display! {exception}")

        return did_update_successfully
    
    @staticmethod
    def condense_logs(logs: list[str], max_message_size: int = 2000) -> list[str]:
        """
        Condense the lines in `logs` into a smaller number of elements of maximum size `max_message_size` - each line is still separated by a new line.

        By default the `max_message_size` is 2000 because I remember that's what Discord says it is.
        """
        condensed_messages: list[str] = []
        while len(logs) > 0:
            condensed_message = ""
            while len(logs) > 0 and len(condensed_message) + len(logs[0] + "\n") < max_message_size:
                condensed_message += (logs.pop(0) + "\n")
            condensed_messages.append(condensed_message)

        return condensed_messages
    
    async def update_server_log_display(self, new_server_logs: list[str]) -> bool:
        """
        Sends the `new_server_logs` messages to the Discord channel specified by `self.logs_dump_channel_id` in as few messages as possible (via `condense_logs`).

        Returns True if the display was successfully updated, False otherwise.
        """
        did_update_successfully = True

        try:
            server_logs_display_channel = self.discord_bot.get_channel(self.logs_dump_channel_id)
            assert type(server_logs_display_channel) == TextChannel, "The server logs dump channel ID should be the ID of a text channel."
            condensed_server_logs = self.condense_logs(new_server_logs)
            
            server_log_write_tasks = [server_logs_display_channel.send(content=log) for log in condensed_server_logs]

            log_update_responses: list[Message | BaseException] = await asyncio.gather(*server_log_write_tasks, return_exceptions=True)

            for response in log_update_responses:
                if isinstance(response, BaseException):
                    did_update_successfully = False
                    logging.error(f"Error when updating server log display: {response}")
        except Exception as exception:
            did_update_successfully = False
            logging.error(f"Unhandled exception when trying to update server log display! {exception}")

        return did_update_successfully

    async def update_chat_log_display(self, new_chat_logs: list[str]) -> bool:
        """
        Sends the `new_chat_logs` messages to the Discord channel specified by `self.chat_dump_channel_id` in as few messages as possible (via `condense_logs`).

        Returns True if the display was successfully updated, False otherwise.
        """
        did_update_successfully = True

        try:
            chat_logs_display_channel = self.discord_bot.get_channel(self.chat_dump_channel_id)
            assert type(chat_logs_display_channel) == TextChannel, "The chat logs dump channel ID should be the ID of a text channel."
            condensed_server_logs = self.condense_logs(new_chat_logs)
            
            chat_log_write_tasks = [chat_logs_display_channel.send(content=log) for log in condensed_server_logs]

            chat_log_update_responses: list[Message | BaseException] = await asyncio.gather(*chat_log_write_tasks, return_exceptions=True)

            for response in chat_log_update_responses:
                if isinstance(response, BaseException):
                    did_update_successfully = False
                    logging.error(f"Error when updating chat log display: {response}")
        except Exception as exception:
            did_update_successfully = False
            logging.error(f"Unhandled exception when trying to update chat log display! {exception}")

        return did_update_successfully
