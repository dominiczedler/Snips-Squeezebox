import LMSTools
import requests
import json
import re


class Device:
    def __init__(self, device_dict):
        self.name = device_dict['name']
        self.names_list = device_dict['names_list']
        self.synonym = device_dict['synonym']
        self.bluetooth = device_dict['bluetooth']
        self.mac = device_dict['squeezelite_mac']
        self.soundcard = device_dict['soundcard']
        self.player = None
        self.auto_pause = False


class Site:
    def __init__(self):
        self.room_name = None
        self.site_id = None
        self.area = None
        self.auto_pause = None
        self.default_device_name = None
        self.devices_dict = dict()
        self.pending_action = dict()

    def update(self, data, server):
        self.room_name = data['room_name']
        self.site_id = data['site_id']
        self.area = data['area']
        self.auto_pause = data['auto_pause']
        self.default_device_name = data['default_device']

        for device_dict in data['devices']:
            if device_dict['squeezelite_mac'] not in self.devices_dict:
                device = Device(device_dict)
                self.devices_dict[device.mac] = device

            device = self.devices_dict[device_dict['squeezelite_mac']]
            device.name = device_dict['name']
            device.names_list = device_dict['names_list']
            device.synonym = device_dict['synonym']
            device.bluetooth = device_dict['bluetooth']
            device.mac = device_dict['squeezelite_mac']
            device.soundcard = device_dict['soundcard']
            try:
                device.player = LMSTools.LMSPlayer(device.mac, server)
            except requests.ConnectionError:
                device.player = None

    def get_devices(self, slot_dict, default_device):
        if slot_dict.get('device'):
            if slot_dict.get('device') == "alle":
                found = [self.devices_dict[mac] for mac in self.devices_dict]
                if not found:
                    return f"Im Raum {self.room_name} gibt es keine Geräte.", None
            else:
                found = [self.devices_dict[mac] for mac in self.devices_dict
                         if slot_dict['device'] in self.devices_dict[mac].names_list]
        else:
            found = [self.devices_dict[mac] for mac in self.devices_dict
                     if default_device in self.devices_dict[mac].names_list]
        if not found:
            return f"Dieses Gerät gibt es im Raum {self.room_name} nicht.", None
        else:
            return None, found


class LMSController:
    def __init__(self, mqtt_client, lms_host, lms_port):
        self.mqtt_client = mqtt_client
        self.server = LMSTools.LMSServer(lms_host, lms_port)
        self.sites_dict = dict()
        self.pending_actions = dict()
        self.current_status = dict()

    def get_music_names(self):
        try:
            all_titles = list()
            titles = self.server.request(params="titles list")
            if titles.get('count') >= 1:
                for title_dict in titles.get('titles_loop'):
                    title = title_dict['title']
                    if title not in all_titles:
                        all_titles.append(title)

            all_albums = list()
            albums = self.server.request(params="albums list")
            if albums.get('count') >= 1:
                for album_dict in albums.get('albums_loop'):
                    album = album_dict['album']
                    if album not in all_albums:
                        all_albums.append(album)

            all_artists = list()
            artists = self.server.request(params="artists list")
            if artists.get('count') >= 1:
                for artist_dict in artists.get('artists_loop'):
                    for artist in re.split(r'; |;|, |,', artist_dict['artist']):
                        if artist and artist not in all_artists:
                            all_artists.append(artist)

            all_genres = list()
            genres = self.server.request(params="genres list")
            if genres.get('count') >= 1:
                for genre_dict in genres.get('genres_loop'):
                    for genre in re.split(r'; |;|, |,|/| / ', genre_dict['genre']):
                        if genre and genre not in all_genres:
                            all_genres.append(genre)

            all_playlists = list()
            playlists = self.server.request(params="playlists list")
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

    def get_site(self, request_siteid, slot_dict=None):
        if slot_dict and slot_dict.get('room'):
            if slot_dict.get('room') == "hier":
                if not self.sites_dict.get(request_siteid):
                    return "Dieser Raum hier wurde noch nicht konfiguriert.", None
                else:
                    return None, self.sites_dict[request_siteid]
            elif slot_dict.get('room') == "alle":
                # TODO: return all sites
                return None, self.sites_dict[request_siteid]
            else:
                dict_rooms = {self.sites_dict[siteid].room_name: self.sites_dict[siteid]
                              for siteid in self.sites_dict}
                if slot_dict.get('room') not in dict_rooms:
                    return f"Der Raum {slot_dict.get('room')} wurde noch nicht konfiguriert.", None
                else:
                    return None, dict_rooms[slot_dict.get('rooms')]
        else:
            if not self.sites_dict.get(request_siteid):
                return "Dieser Raum hier wurde noch nicht konfiguriert.", None
            else:
                return None, self.sites_dict[request_siteid]

    def get_all_site_names(self):
        all_rooms = list()
        all_devices = list()
        all_areas = list()
        for site_id in self.sites_dict:
            if self.sites_dict[site_id].room_name not in all_rooms:
                all_rooms.append(self.sites_dict[site_id].room_name)

            if self.sites_dict[site_id].area not in all_areas:
                all_areas.append(self.sites_dict[site_id].area)

            for device_name in self.sites_dict[site_id].devices_dict:
                device = self.sites_dict[site_id].devices_dict[device_name]
                for name in device.names_list:
                    if name not in all_devices:
                        all_devices.append(name)
        all_names = {
            'rooms': all_rooms,
            'areas': all_areas,
            'devices': all_devices
        }
        return all_names

    def get_player(self, site_info):
        player = self.server.get_player_from_name(site_info['room_name'])
        if player:
            return None, player
        else:
            return "Diesen Player gibt es nicht.", None

    def new_music(self, slot_dict, request_siteid):

        err, site = self.get_site(request_siteid, slot_dict)
        if err:
            return err

        err, devices = site.get_devices(slot_dict, site.default_device_name)
        if err:
            return err

        device = devices[0]  # TODO: Start same music on multiple devices

        if not site.pending_action:
            # Connect bluetooth device if necessary
            print(device.bluetooth)
            if device.bluetooth and not device.bluetooth['is_connected']:
                site.pending_action = {'action': "new_music",
                                       'slot_dict': slot_dict,
                                       'request_siteid': request_siteid}

                self.mqtt_client.publish(f'squeezebox/request/oneSite/{site.site_id}/deviceConnect',
                                         json.dumps({'addr': device.bluetooth['addr'],
                                                     'squeeze_mac': device.mac,
                                                     'soundcard': device.soundcard,
                                                     'name': device.synonym}))
                return None
        else:
            site.pending_action = None

        player = device.player
        if not player:
            for i in range(3):
                try:
                    player = LMSTools.LMSPlayer(device.mac, self.server)
                    if player:
                        break
                except requests.ConnectionError:
                    player = None
        if not player:
            return "Das Abspielprogramm konnte auf dem Gerät nicht gestartet werden."

        try:
            query_params = list()
            artist = slot_dict.get('artist')
            album = slot_dict.get('album')
            title = slot_dict.get('title')
            genre = slot_dict.get('genre')
            if album or title:
                if artist:
                    query_params.append(f"contributor.namesearch={'+'.join(artist.split(' '))}")
                if album:
                    query_params.append(f"album.titlesearch={'+'.join(album.split(' '))}")
                if title:
                    query_params.append(f"track.titlesearch={'+'.join(title.split(' '))}")
                if genre:
                    query_params.append(f"genre.namesearch={'+'.join(genre.split(' '))}")
                player.request(f"playlist shuffle 0")
                player.request(f"playlist loadtracks {'&'.join(query_params)}")
            elif artist:
                query_params = [f"contributor.namesearch={'+'.join(artist.split(' '))}"]
                player.request("playlist shuffle 1")
                player.request(f"playlist loadtracks {'&'.join(query_params)}")
            elif genre:
                player.request("randomplaygenreselectall 0")
                player.request(f"randomplaychoosegenre {genre} 1")
                player.request("randomplay tracks")
            else:
                player.request("randomplaygenreselectall 1")
                player.request("randomplay tracks")

            return None

        except requests.exceptions.ConnectionError:
            return "Es konnte keine Verbindung zum Musik Server hergestellt werden."

    def pause_music(self, slot_dict, request_siteid):
        err, site = self.get_site(request_siteid, slot_dict)
        if err:
            return
        err, devices = site.get_devices(slot_dict, site.default_device_name)
        if err:
            return
        for d in devices:
            if d.player:
                d.auto_pause = False
                d.player.pause()
        return

    def play_music(self, slot_dict, request_siteid):
        err, site = self.get_site(request_siteid, slot_dict)
        if err:
            return
        err, devices = site.get_devices(slot_dict, site.default_device_name)
        if err:
            return
        for d in devices:
            if d.player and d.player.mode in ["pause", "stop"]:
                d.auto_pause = False
                d.player.play(1.1)
        return

    def change_volume(self, slot_dict, request_siteid):
        err, site = self.get_site(request_siteid, slot_dict)
        if err:
            return
        err, devices = site.get_devices(slot_dict, site.default_device_name)
        if err:
            return
        for d in devices:
            if d.player:
                if slot_dict.get('volume_absolute'):
                    d.player.volume = slot_dict.get('volume_absolute')
                elif slot_dict.get('direction') == "lower":
                    if slot_dict.get('volume_change'):
                        d.player.volume_down(slot_dict.get('volume_change'))
                    else:
                        d.player.volume_down(10)
                elif slot_dict.get('direction') == "higher":
                    if slot_dict.get('volume_change'):
                        d.player.volume_up(slot_dict.get('volume_change'))
                    else:
                        d.player.volume_up(10)
                elif slot_dict.get('direction') == "low":
                    d.player.volume = 30
                elif slot_dict.get('direction') == "high":
                    d.player.volume = 70
                elif slot_dict.get('direction') == "lowest":
                    d.player.volume = 10
                elif slot_dict.get('direction') == "highest":
                    d.player.volume = 100
        return
