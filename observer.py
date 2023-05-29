
import mcstatus
import asyncio
import logging
from dataclasses import dataclass, field
import datetime
import aiofiles
from mcrcon import MCRcon

@dataclass
class ServerStatusResponse:
    timestamp: float
    is_online: bool = False
    online_player_count: int = -1
    online_player_limit: int = -1
    online_player_names: list[str] = field(default_factory=list)
    version: str = ""

    def is_equal_to(self, other_status_response: "ServerStatusResponse") -> bool:
        """
        Compares this object to another `ServerStatusResponse` object and returns True if their contents (all fields besides `timestamp`) are identical, False otherwise
        """
        is_equal = True

        if any([
            self.is_online != other_status_response.is_online,
            self.online_player_count != other_status_response.online_player_count,
            self.online_player_limit != other_status_response.online_player_limit,
            len(set(self.online_player_names) ^ set(other_status_response.online_player_names)) > 0, # Checking if the two online_player_names lists have any unique elements in each
            self.version != other_status_response.version
        ]):
            is_equal = False

        return is_equal

@dataclass
class ServerLogsResponse:
    timestamp: float
    server_logs: list[str] = field(default_factory=list)

    def is_equal_to(self, other_logs_response: "ServerLogsResponse") -> bool:
        """
        Compares this object to another `ServerLogsResponse` object and returns True if their contents (all fields besides `timestamp`) are identical, False otherwise
        """
        is_equal = True

        if any([
            len(self.server_logs) != len(other_logs_response.server_logs),
            len(set(self.server_logs) ^ set(other_logs_response.server_logs)) > 0, # Checking if the two server_logs lists have any unique elements in each
        ]):
            is_equal = False

        return is_equal

@dataclass
class ServerResponse:
    timestamp: float
    status_info: ServerStatusResponse
    logs_info: ServerLogsResponse

    def is_equal_to(self, other_server_response: "ServerResponse") -> bool:
        """
        Compares this object to another `ServerResponse` object and returns True if their contents (all fields besides `timestamp`) are identical, False otherwise
        """
        is_equal = True

        if any([
            self.status_info.is_equal_to(other_server_response.status_info) is False,
            self.logs_info.is_equal_to(other_server_response.logs_info) is False,
        ]):
            is_equal = False

        return is_equal

def get_current_timestamp() -> float:
    """Returns the current POSIX timestamp. Shorthand."""

    return datetime.datetime.now().timestamp()

class Server:
    ip: str
    port: int
    rcon_password: str
    rcon_port: int
    is_query_enabled: bool
    server_log_file_name: str
    server: mcstatus.JavaServer
    player_list: list[str]
    most_recent_response: ServerResponse | None

    def __init__(self, ip: str, rcon_password: str, server_log_file_name: str, port: int = 25565, rcon_port: int = 25575, is_query_enabled: bool = False) -> None:
        """
        Initialize `Server` object.

        :param str ip: The IP address of the server (no port number) - this can be `localhost`
        :param int port: The port of the server, default 25565
        :param int rcon_port: The port on which the server accepts rcon, default 25575
        :param str rcon_password: The password for using rcon with the server
        :param bool is_query_enabled: Whether the server is configured to accept queries (see the `enable-query` line in `server.properties`), default False
        :param str server_log_file_name: The location/file name of the `latest.log` file to read from.

        If queries are enabled it enables us to read the entirety of the player list rather than a small selection.
        """
        self.ip = ip
        self.port = port

        SERVER_ADDRESS = f"{ip}:{port}"
        self.server = mcstatus.JavaServer.lookup(SERVER_ADDRESS)

        self.server_log_file_name = server_log_file_name

        self.rcon_password = rcon_password
        self.rcon_port = rcon_port

        self.is_query_enabled = is_query_enabled

        self.player_list = []
        self.most_recent_response = None
    
    async def _ping_server_status(self) -> ServerStatusResponse:
        """
        Pings the server via query protocol if possible or ping protocol otherwise, returning information about the server.
        """

        is_online = False
        online_player_limit: int = -1
        online_player_count: int = -1
        online_player_names: list[str] = []
        version = ""

        try:
            if self.is_query_enabled:
                query = await self.server.async_query()
                online_player_limit = query.players.max
                online_player_count = query.players.online
                online_player_names = query.players.names
                version = query.software.version
            else:
                status = await self.server.async_status()
                online_player_limit = status.players.max
                online_player_count = status.players.online
                online_player_names = [player.name for player in (status.players.sample or [])]
                version = status.version.name
            is_online = True
        except asyncio.exceptions.TimeoutError as exception:
            logging.warning("Querying the server timed out.")
        except Exception as exception:
            logging.error(f"Unhandled exception pinging server status! {exception}")
        
        server_status_response = ServerStatusResponse(
            timestamp = get_current_timestamp(),
            is_online = is_online,
            online_player_count = online_player_count,
            online_player_limit = online_player_limit,
            online_player_names = online_player_names,
            version = version
        )

        return server_status_response

    async def _ping_server_logs(self) -> ServerLogsResponse:
        """
        Reads the file of server logs and returns them with some auxiliary information.
        """
        all_server_logs: list[str] = []

        try:
            async with aiofiles.open(self.server_log_file_name, "r") as server_log_file:
                all_server_logs = await server_log_file.readlines()
        except FileNotFoundError as exception:
            logging.error(f"Server log file {self.server_log_file_name} not found! {exception}")
        except Exception as exception:
            logging.error(f"Unhandled exception reading from server logs file! {exception}")

        server_logs_response = ServerLogsResponse(
            timestamp = get_current_timestamp(),
            server_logs = all_server_logs,
        )

        return server_logs_response

    async def ping_server(self) -> ServerResponse:
        """
        Pings server status and server logs, combines them into one data object, and returns it
        """
        status_response = ServerStatusResponse(timestamp=get_current_timestamp())
        logs_response = ServerLogsResponse(timestamp=get_current_timestamp())

        ping_status_task = self._ping_server_status()
        ping_logs_task = self._ping_server_logs()
        try:
            status_response, logs_response = await asyncio.gather(ping_status_task, ping_logs_task)
        except Exception as exception:
            logging.error(f"Unhandled exception pinging server! {exception}")

        server_response_object = ServerResponse(
            timestamp = get_current_timestamp(),
            status_info = status_response,
            logs_info = logs_response
        )

        self.most_recent_response = server_response_object

        return server_response_object

    async def send_chat_message(self, sender_name: str, message_contents: str) -> bool:
        """
        Attempts to use RCON to send the chat message to the server.

        Returns True if successful, False if not.
        """
        did_successfully_send_message = True

        command = '/tellraw @a ["",{"text":"' + f"[{sender_name}] " + '","color":"aqua"},{"text":"' + message_contents + '"}]'

        try:
            with MCRcon(host=self.ip, port=self.rcon_port, password=self.rcon_password) as mcr:
                response = mcr.command(command)
        except Exception as exception:
            did_successfully_send_message = False
            logging.error(f"Unhandled exception sending a chat message to the server: {exception}")

        return did_successfully_send_message
    
    async def run_console_command(self, command: str) -> bool:
        """
        Attempts to use RCON to send a console command to the server.

        Returns True is successful, False if not.
        """
        did_successfully_send_message = True

        try:
            with MCRcon(host=self.ip, port=self.rcon_port, password=self.rcon_password) as mcr:
                response = mcr.command(command)
        except Exception as exception:
            did_successfully_send_message = False
            logging.error(f"Unhandled exception sending a chat message to the server: {exception}")

        return did_successfully_send_message

if __name__ == "__main__":
    server = Server("70.172.34.123", "interc3pt", r"D:/Samihan/Documents/Programming/Python Projects/Remote Minecraft Bridgebot/logs")
    asyncio.run(server.ping_server())