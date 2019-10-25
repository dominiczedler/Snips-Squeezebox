"""
Simple python class definitions for interacting with Logitech Media Server.
This code uses the JSON interface.
"""

import requests
from .player import LMSPlayer


class LMSConnectionError(Exception):
    pass


class LMSServer(object):
    """
    :type host: str
    :param host: address of LMS server (default "localhost")
    :type port: int
    :param port: port for the web interface (default 9000)
    Class for Logitech Media Server.
    Provides access via JSON interface. As the class uses the JSON interface, no active connections are maintained.
    """

    def __init__(self, host="localhost", port=9000):
        self.host = host
        self.port = port
        self._version = None
        self.id = 1
        self.web = "http://{h}:{p}/".format(h=host, p=port)
        self.url = "http://{h}:{p}/jsonrpc.js".format(h=host, p=port)

    def request(self, player="-", params=None):
        """
        :type player: str
        :param player: MAC address of a connected player. Alternatively, "-" can be used for server level requests.
        :type params: str or list
        :param params: Request command
        """
        if type(params) == str:
            params = params.split()

        cmd = [player, params]

        data = {"id": self.id,
                "method": "slim.request",
                "params": cmd}

        req = requests.get(self.url, headers={'Content-Type': 'application/json'}, json=data)
        response = req.json()
        self.id += 1
        return response.get("result")

    def get_players(self):
        """
        :rtype: list
        :returns: list of LMSPlayer instances
        Return a list of currently connected Squeezeplayers.
        """
        players = []
        player_count = self.get_player_count()
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

    def get_player_count(self):
        """
        :rtype: int
        :returns: number of connected players
        """
        try:
            count = self.request(params="player count ?")["_count"]
        except LMSConnectionError:
            count = 0
        return count

    def get_sync_groups(self):
        """
        :rtype: list
        :returns: list of syncgroups. Each group is a list of references of the members.
        """
        try:
            groups = self.request(params="syncgroups ?")
            syncgroups = [x.get("sync_members", "").split(",") for x in groups.get("syncgroups_loop", dict())]
        except LMSConnectionError:
            syncgroups = None
        return syncgroups

    def show_players_sync_status(self):
        """
        :rtype: dict
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

    def ping(self):
        """
        :rtype: bool
        :returns: True if server is alive, False if server is unreachable
        Method to test if server is active.
        """

        try:
            self.request(params="version ?")
            return True
        except LMSConnectionError:
            return False

    @property
    def version(self):
        """
        :attr version: Version number of server Software
        """
        if self._version is None:
            try:
                self._version = self.request(params="version ?")["_version"]
            except LMSConnectionError:
                self._version = None
        return self._version

    def rescan(self, mode='fast'):
        """
        :type mode: str
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

    def get_music_names(self):
        try:
            all_titles = list()
            titles = self.request(params="titles list")
            if titles.get('count') >= 1:
                for title_dict in titles.get('titles_loop'):
                    title = title_dict['title']
                    if title not in all_titles:
                        all_titles.append(title)

            all_albums = list()
            albums = self.request(params="albums list")
            if albums.get('count') >= 1:
                for album_dict in albums.get('albums_loop'):
                    album = album_dict['album']
                    if album not in all_albums:
                        all_albums.append(album)

            all_artists = list()
            artists = self.request(params="artists list")
            if artists.get('count') >= 1:
                for artist_dict in artists.get('artists_loop'):
                    for artist in re.split(r'; |;|, |,', artist_dict['artist']):
                        if artist and artist not in all_artists:
                            all_artists.append(artist)

            all_genres = list()
            genres = self.request(params="genres list")
            if genres.get('count') >= 1:
                for genre_dict in genres.get('genres_loop'):
                    for genre in re.split(r'; |;|, |,|/| / ', genre_dict['genre']):
                        if genre and genre not in all_genres:
                            all_genres.append(genre)

            all_playlists = list()
            playlists = self.request(params="playlists list")
            if playlists.get('count') >= 1:
                for playlist_dict in playlists.get('playlists_loop'):
                    playlist = playlist_dict['playlist']
                    if playlist not in all_playlists:
                        all_playlists.append(playlist)

            all_names = {
                'titles': all_titles,
                'albums': all_albums,
                'artists': all_artists,
                'genres': all_genres,
                'playlists': all_playlists
            }
            return False, all_names

        except requests.exceptions.ConnectionError:
            return True, None
