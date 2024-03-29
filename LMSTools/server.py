"""
Simple python class definitions for interacting with Logitech Media Server.
This code uses the JSON interface.
"""

import requests
from .player import LMSPlayer
from typing import Union


class LMSConnectionError(Exception):
    pass


class LMSServer(object):
    """
    :param host: address of LMS server
    :param port: port for the web interface
    Class for Logitech Media Server.
    Provides access via JSON interface. As the class uses the JSON interface, no active connections are maintained.
    """

    def __init__(self, host: str = "localhost", port: int = 9000, username: str = "", password: str = ""):
        self.host = host
        self.port = port
        self._version = None
        self.id = 1
        self.url = f"http://{username}:{password}@{host}:{port}/jsonrpc.js"

    def request(self, player: str = "-", params: Union[str, list] = None) -> dict:
        """
        :param player: MAC address of a connected player. Alternatively, "-" can be used for server level requests.
        :param params: Request command
        """
        if isinstance(params, str):
            params = params.split()

        cmd = [player, params]

        data = {"id": self.id,
                "method": "slim.request",
                "params": cmd}

        req = requests.get(self.url, headers={'Content-Type': 'application/json'}, json=data)
        response = req.json()
        self.id += 1
        return response.get("result")

    def get_players(self) -> list:
        """
        :returns: list of LMSPlayer instances
        Return a list of currently connected Squeezeplayers.
        """
        players = []
        player_count = int(self.get_player_count())
        for i in range(player_count):
            player = LMSPlayer.from_index(i, self)
            players.append(player)
        return players

    def get_player_from_name(self, name):
        players = self.get_players()
        found = [player for player in players if player.name == name]
        if found:
            return found[0]
        else:
            return None

    def get_player_count(self) -> int:
        """
        :returns: number of connected players
        """
        try:
            count = self.request(params="player count ?")["_count"]
        except LMSConnectionError:
            count = 0
        return count

    def get_info_total(self, info_type: str) -> int:
        """
        :returns: number of unique items in database
        """
        try:
            count = self.request(params=f"info total {info_type} ?")["_count"]
        except requests.ConnectionError:
            count = 0
        return count

    def get_sync_groups(self) -> list:
        """
        :returns: list of syncgroups. Each group is a list of references of the members.
        """
        try:
            groups = self.request(params="syncgroups ?")
            syncgroups = [x.get("sync_members", "").split(",") for x in groups.get("syncgroups_loop", dict())]
        except LMSConnectionError:
            syncgroups = None
        return syncgroups

    def show_players_sync_status(self) -> dict:
        """
        :returns: dictionary (see attributes below)
        :attr group_count: (int) Number of sync groups
        :attr player_count: (int) Number of connected players
        :attr players: (list) List of players (see below)
        Player object (dict)
        :attr name: Name of player
        :attr ref: Player reference
        :attr sync_index: Index of sync group (-1 if not synced)
        """
        players = self.get_players()
        groups = self.get_sync_groups()

        all_players = []

        for player in players:
            item = {"name": player.name,
                    "ref": player.ref}
            index = [i for i, g in enumerate(groups) if player.ref in g]
            if index:
                item["sync_index"] = index[0]
            else:
                item["sync_index"] = -1
            all_players.append(item)

        sync_status = {"group_count": len(groups),
                       "player_count": len(players),
                       "players": all_players}
        return sync_status

    def sync(self, master, slave):
        """
        :type master: (ref)
        :param master: Reference of the player to which you wish to sync another player
        :type slave: (ref)
        :param slave: Reference of the player which you wish to sync to the master
        Sync squeezeplayers.
        """
        try:
            self.request(player=master, params=["sync", slave])
            return True
        except LMSConnectionError:
            return False

    def connected(self) -> bool:
        """
        :returns: True if server is alive, False if server is unreachable
        Method to test if server is active.
        """

        try:
            self.request(params="version ?")
            return True
        except LMSConnectionError:
            return False

    @property
    def version(self) -> str:
        """
        :returns: Version number of server Software
        """
        if self._version is None:
            try:
                self._version = self.request(params="version ?")["_version"]
            except LMSConnectionError:
                self._version = None
        return self._version

    def rescan(self, mode: str = 'fast'):
        """
        :param mode: Mode can be 'fast' for update changes on library, 'full' for complete library scan and 'playlists'
        for playlists scan only.
        Trigger rescan of the media library.
        """
        try:
            is_scanning = bool(self.request("rescan ?")["_rescan"])
            if not is_scanning:
                if mode == 'fast':
                    return self.request(params="rescan")
                elif mode == 'full':
                    return self.request(params="wipecache")
                elif mode == 'playlists':
                    return self.request(params="rescan playlists")
            else:
                return ""
        except LMSConnectionError:
            return None

    @property
    def rescanprogress(self):
        """
        :attr rescanprogress: current rescan progress
        """
        try:
            progress = self.request(params="rescanprogress")["_rescan"]
        except LMSConnectionError:
            progress = None
        return progress
