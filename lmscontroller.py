import LMSTools
import json
import re
import random


class Device:
    def __init__(self, player):
        self.name = str()
        self.site_id = str()
        self.names_list = list()
        self.synonyms = list()
        self.bluetooth = dict()
        self.mac = str()
        self.soundcard = str()
        self.player = player
        self.auto_pause = False


class Site:
    def __init__(self):
        self.room_name = None
        self.site_id = None
        self.area = None
        self.auto_pause = None
        self.default_device_name = None
        self.devices_dict = dict()
        self.active_device = None
        self.pending_action = dict()
        self.need_connection_queue = list()
        self.need_service_queue = list()
        self.action_target = None
        self.action_target_args = None

    def update(self, data, server):
        self.room_name = data['room_name']
        self.site_id = data['site_id']
        self.area = data['area']
        self.auto_pause = data['auto_pause']
        self.default_device_name = data['default_device']

        for device_dict in data['devices']:
            if not self.devices_dict.get('squeezelite_mac'):
                player = LMSTools.LMSPlayer(device_dict['squeezelite_mac'], server, False, device_dict['name'])
                self.devices_dict[device_dict['squeezelite_mac']] = Device(player)

            device = self.devices_dict[device_dict['squeezelite_mac']]
            device.name = device_dict['name']
            device.site_id = self.site_id
            device.names_list = device_dict['names_list']
            device.synonyms = device_dict['synonyms']
            device.bluetooth = device_dict['bluetooth']
            device.mac = device_dict['squeezelite_mac']
            device.soundcard = device_dict['soundcard']

    def get_device(self, slot_dict, default_device):
        if slot_dict.get('device'):
            if slot_dict.get('device') == "alle":
                return f"Es geht nur ein Gerät pro Raum.", None
            else:
                found = [self.devices_dict[mac] for mac in self.devices_dict
                         if slot_dict['device'] in self.devices_dict[mac].names_list]
        else:
            found = [self.devices_dict[mac] for mac in self.devices_dict
                     if default_device in self.devices_dict[mac].names_list]

        if not found:
            return f"Dieses Gerät gibt es im Raum {self.room_name} nicht.", None
        else:
            return None, found[0]


class LMSController:
    def __init__(self, mqtt_client, lms_host, lms_port):
        self.mqtt_client = mqtt_client
        self.server = LMSTools.LMSServer(lms_host, lms_port)
        self.sites_dict = dict()
        self.pending_actions = dict()
        self.current_status = dict()

    def get_inject_operations(self, requested_type: str) -> (str, list):
        if not self.server.connected():
            err = "Die Namen konnten nicht gesammelt werden. Es besteht keine Verbindung zum Medien Server."
            return err, None

        if requested_type:
            if requested_type == "music":
                requested_types = ["album", "artist", "title", "playlist", "genre"]
            elif requested_type == "favorite":
                requested_types = ["radio", "podcast"]
            else:
                requested_types = [requested_type]
        else:
            requested_types = ["device", "room", "area", "album", "artist",
                               "title", "playlist", "genre", "radio", "podcast"]

        operations = list()
        if "title" in requested_types:
            titles = self.get_music_titles()
            if titles:
                operations.append(('addFromVanilla', {'squeezebox_titles': titles}))
        if "artist" in requested_types:
            artists = self.get_music_artists()
            if artists:
                operations.append(('addFromVanilla', {'squeezebox_artists': artists}))
        if "album" in requested_types:
            albums = self.get_music_albums()
            if albums:
                operations.append(('addFromVanilla', {'squeezebox_albums': albums}))
        if "genre" in requested_types:
            genres = self.get_music_genres()
            if genres:
                operations.append(('addFromVanilla', {'squeezebox_genres': genres}))
        if "playlist" in requested_types:
            playlists = self.get_music_playlists()
            if playlists:
                operations.append(('addFromVanilla', {'squeezebox_playlists': playlists}))
        if "radio" in requested_types:
            radios = self.get_radio_stations()
            if radios:
                operations.append(('addFromVanilla', {'squeezebox_radios': radios}))
        if "podcast" in requested_types:
            podcasts = self.get_podcast_titles()
            if podcasts:
                operations.append(('addFromVanilla', {'squeezebox_podcasts': podcasts}))
        if "device" in requested_types:
            devices = self.get_site_names('devices')
            if devices:
                operations.append(('addFromVanilla', {'audio_devices': devices}))
        if "rooms" in requested_types:
            rooms = self.get_site_names('rooms')
            if rooms:
                operations.append(('addFromVanilla', {'squeezebox_rooms': rooms}))
        if "area" in requested_types:
            areas = self.get_site_names('areas')
            if areas:
                operations.append(('addFromVanilla', {'squeezebox_areas': areas}))

        if not operations:
            return "Es gibt nichts hinzuzufügen.", None
        else:
            return None, operations

    def get_music_albums(self) -> list:
        all_albums = list()
        albums = self.server.request(params="albums list")
        if albums.get('count') >= 1:
            for album_dict in albums.get('albums_loop'):
                album = album_dict['album']
                if album not in all_albums:
                    all_albums.append(album)
        return all_albums

    def get_music_titles(self) -> list:
        all_titles = list()
        titles = self.server.request(params="titles list")
        if titles.get('count') >= 1:
            for title_dict in titles.get('titles_loop'):
                title = title_dict['title']
                if title not in all_titles:
                    all_titles.append(title)
        return all_titles

    def get_music_artists(self) -> list:
        all_artists = list()
        artists = self.server.request(params="artists list")
        if artists.get('count') >= 1:
            for artist_dict in artists.get('artists_loop'):
                for artist in re.split(r'; |;|, |,', artist_dict['artist']):
                    if artist and artist not in all_artists:
                        all_artists.append(artist)
        return all_artists

    def get_music_genres(self) -> list:
        all_genres = list()
        genres = self.server.request(params="genres list")
        if genres.get('count') >= 1:
            for genre_dict in genres.get('genres_loop'):
                for genre in re.split(r'; |;|, |,|/| / ', genre_dict['genre']):
                    if genre and genre not in all_genres:
                        all_genres.append(genre)
        return all_genres

    def get_music_playlists(self) -> list:
        all_playlists = list()
        playlists = self.server.request(params="playlists list")
        if playlists.get('count') >= 1:
            for playlist_dict in playlists.get('playlists_loop'):
                playlist = playlist_dict['playlist']
                if playlist not in all_playlists:
                    all_playlists.append(playlist)
        return all_playlists

    def get_radio_stations(self) -> list:
        all_radios = list()
        count = self.server.request(params="favorites items").get('count')
        if count:
            favorite_dicts = self.server.request(params=f"favorites items 0 {count}")['loop_loop']
            music_titles = self.get_music_titles()
            for favorite_dict in favorite_dicts:
                name = favorite_dict['name']
                if name not in all_radios and favorite_dict['isaudio'] and name not in music_titles:
                    all_radios.append(name)
        return all_radios

    def get_podcast_titles(self) -> list:
        all_podcasts = list()
        count = self.server.request(params="favorites items").get('count')
        if count:
            favorite_dicts = self.server.request(params=f"favorites items 0 {count}")['loop_loop']
            music_albums = self.get_music_albums()
            music_artists = self.get_music_artists()
            for favorite_dict in favorite_dicts:
                name = favorite_dict['name']
                if name not in all_podcasts and favorite_dict['hasitems'] \
                        and name not in music_albums and name not in music_artists:
                    all_podcasts.append(name)
        return all_podcasts

    def get_site_names(self, info_type: str) -> list:
        all_names = list()
        if info_type == "devices":
            for site_id in self.sites_dict:
                for device_name in self.sites_dict[site_id].devices_dict:
                    device = self.sites_dict[site_id].devices_dict[device_name]
                    for name in device.names_list:
                        if name not in all_names:
                            all_names.append(name)
        elif info_type == "areas":
            for site_id in self.sites_dict:
                if self.sites_dict[site_id].area not in all_names:
                    all_names.append(self.sites_dict[site_id].area)
        elif info_type == "rooms":
            for site_id in self.sites_dict:
                if self.sites_dict[site_id].room_name not in all_names:
                    all_names.append(self.sites_dict[site_id].room_name)
        return all_names

    def get_sites(self, request_siteid, slot_dict=None, single=False, room_slot='room'):
        # TODO: Look at area slot
        if slot_dict and slot_dict.get(room_slot):
            room_slot_value = slot_dict.get(room_slot)
            if room_slot_value == "hier":
                if not self.sites_dict.get(request_siteid):
                    return "Dieser Raum hier wurde noch nicht konfiguriert.", None
                else:
                    return None, [self.sites_dict[request_siteid]]
            elif room_slot_value == "alle":
                if not single:
                    return None, [self.sites_dict[site_id] for site_id in self.sites_dict]
                else:
                    return "Diese Funktion gibt es nicht.", None
            else:
                dict_rooms = {self.sites_dict[siteid].room_name: self.sites_dict[siteid]
                              for siteid in self.sites_dict}
                if room_slot_value not in dict_rooms:
                    return f"Der Raum {room_slot_value} wurde noch nicht konfiguriert.", None
                else:
                    return None, [dict_rooms[room_slot_value]]
        else:
            if not self.sites_dict.get(request_siteid):
                return "Dieser Raum hier wurde noch nicht konfiguriert.", None
            else:
                return None, [self.sites_dict[request_siteid]]

    def make_devices_ready(self, slot_dict, request_siteid, target=None, args=()):
        if not self.server.connected:
            return "Es konnte keine Verbindung zum Musik Server hergestellt werden."

        request_site = self.sites_dict.get(request_siteid)
        if not request_site:
            return "Dieser Raum hier wurde noch nicht konfiguriert."

        err, sites = self.get_sites(request_siteid, slot_dict)
        if err:
            return err

        if not request_site.action_target:
            request_site.action_target = target
            request_site.action_target_args = args
            request_site.need_connection_queue = list()
            request_site.need_service_queue = list()

            for site in sites:
                err, device = site.get_device(slot_dict, site.default_device_name)
                if err:
                    return err
                if device.bluetooth and not device.bluetooth['is_connected']:
                    request_site.need_connection_queue.append(device)
                if not device.player.connected:
                    request_site.need_service_queue.append(device)

        if request_site.need_connection_queue:
            for device in request_site.need_connection_queue:
                site = self.sites_dict[device.site_id]
                site.pending_action = {
                    'slot_dict': slot_dict,
                    'request_siteid': request_siteid,
                    'device': device,
                }
                payload = {  # information for bluetooth connection
                    'addr': device.bluetooth['addr'],
                    'tries': 3
                }
                self.mqtt_client.publish(  # request bluetooth connection
                    f'bluetooth/request/oneSite/{site.site_id}/deviceConnect',
                    json.dumps(payload)
                )
            return None

        if request_site.need_service_queue:
            for device in request_site.need_service_queue:
                site = self.sites_dict[device.site_id]

                site.pending_action = {
                    'slot_dict': slot_dict,
                    'request_siteid': request_siteid,
                    'device': device
                }

                client_name = site.room_name
                areas = list()
                for site_id in self.sites_dict:
                    area = self.sites_dict[site_id].area
                    if area not in areas:
                        areas.append(area)
                if len(areas) > 1:
                    client_name += f"-{site.area}"
                if device.synonyms:
                    client_name += f"-{device.synonyms[0]}"
                else:
                    client_name += f"-{device.name}"

                payload = {  # information for squeezelite service
                    'server': self.server.host,
                    'squeeze_mac': device.mac,
                    'soundcard': device.soundcard,
                    'name': client_name
                }
                self.mqtt_client.publish(
                    f'squeezebox/request/oneSite/{site.site_id}/serviceStart',
                    json.dumps(payload)
                )
            return None

        for site in sites:
            err, device = site.get_device(slot_dict, site.default_device_name)
            if err:
                return err
            site.active_device = device

        if request_site.action_target:  # Call target function after all queues
            result = request_site.action_target(*request_site.action_target_args)
            request_site.action_target = None
            request_site.action_target_args = None
            return result

    def get_player_and_sync(self, slot_dict, request_siteid):
        err, sites = self.get_sites(request_siteid, slot_dict)
        if err:
            return err, None

        err, request_site = self.get_sites(request_siteid)
        if err:
            return err, None
        else:
            request_site = request_site[0]

        if len(sites) > 1:
            if request_site in sites:
                player = request_site.active_device.player
                sites.remove(request_site)
            else:
                player = sites[0].active_device.player
                del sites[0]
            player.unsync()
            for site in sites:
                player.sync(player=site.active_device.player)
        else:
            player = sites[0].active_device.player
        return None, player

    def music(self, slot_dict, request_siteid):
        if not self.server.connected():
            return "Der Server ist nicht erreichbar."
        err, player = self.get_player_and_sync(slot_dict, request_siteid)
        if err:
            return err

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
            if genre not in self.get_music_genres():
                return "Zu dieser Stilrichtung gibt es noch keine Musik."
            player.request("randomplaygenreselectall 0")
            player.request(f"randomplaychoosegenre {genre} 1")
            player.request("randomplay tracks")
        else:
            player.request("randomplaygenreselectall 1")
            player.request("randomplay tracks")

        return None

    def podcast(self, slot_dict, request_siteid):
        if not self.server.connected():
            return "Der Server ist nicht erreichbar."
        err, player = self.get_player_and_sync(slot_dict, request_siteid)
        if err:
            return err
        podcast_name = slot_dict.get('podcast')
        result = player.request(f"search items 0 50 search:{'+'.join(podcast_name.split(' '))}")
        if not result.get('count'):
            return "Es gibt keinen solchen Podcast."
        found_podcasts = [item_dict for item_dict in result.get('loop_loop') if item_dict.get('hasitems')]
        if not found_podcasts:
            return "Es gibt nur Radios mit so einem Namen."
        podcast_id = found_podcasts[0].get('id')
        result = player.request(f"search items 0 50 item_id:{podcast_id}.0")
        if not result.get('count'):
            return "Es gibt keine Episoden von diesem Podcast."
        found_episodes = [item_dict for item_dict in result.get('loop_loop') if item_dict.get('isaudio')]
        if not found_episodes:
            return "Es gibt keine Audio Episoden zu diesem Podcast."
        episode_id = found_episodes[0].get('id')  # TODO: Multiple episodes
        player.request(f"podcast playlist play item_id:{episode_id}")

    def radio(self, slot_dict, request_siteid):
        if not self.server.connected():
            return "Der Server ist nicht erreichbar."
        err, player = self.get_player_and_sync(slot_dict, request_siteid)
        if err:
            return err
        station_name = slot_dict.get('radio')
        if not station_name:
            favorite_stations = self.get_radio_stations()
            if not favorite_stations:
                return "Es wurde kein Sender genannt und es gibt keine Sender in den Favoriten."
            station_name = random.choice(favorite_stations)
        result = player.request(f"search items 0 50 search:{'+'.join(station_name.split(' '))}")
        if not result.get('count'):
            return "Es gibt keinen solchen Radiosender."
        found_stations = [item_dict for item_dict in result.get('loop_loop') if not item_dict.get('hasitems')]
        if not found_stations:
            return "Es gibt nur Podcasts mit so einem Namen."
        station_id = found_stations[0].get('id')
        player.request(f"podcast playlist play item_id:{station_id}")

    def player_pause(self, slot_dict, request_siteid):
        err, sites = self.get_sites(request_siteid, slot_dict)
        if err or not self.server.connected():
            return
        for site in sites:
            device = site.active_device
            if device and device.player.connected:
                device.auto_pause = False
                device.player.pause()
        return

    def player_play(self, slot_dict, request_siteid):
        err, sites = self.get_sites(request_siteid, slot_dict)
        if err or not self.server.connected():
            return
        for site in sites:
            device = site.active_device
            if device and device.player.connected and device.player.mode in ["pause", "stop"]:
                device.auto_pause = False
                device.player.play(1.1)
        return

    def player_volume(self, slot_dict, request_siteid):
        err, sites = self.get_sites(request_siteid, slot_dict)
        if err or not self.server.connected():
            return
        for site in sites:
            device = site.active_device
            if device and device.player.connected:
                if slot_dict.get('volume_absolute'):
                    device.player.volume = slot_dict.get('volume_absolute')
                elif slot_dict.get('direction') == "lower":
                    if slot_dict.get('volume_change'):
                        device.player.volume_down(slot_dict.get('volume_change'))
                    else:
                        device.player.volume_down(10)
                elif slot_dict.get('direction') == "higher":
                    if slot_dict.get('volume_change'):
                        device.player.volume_up(slot_dict.get('volume_change'))
                    else:
                        device.player.volume_up(10)
                elif slot_dict.get('direction') == "low":
                    device.player.volume = 30
                elif slot_dict.get('direction') == "high":
                    device.player.volume = 70
                elif slot_dict.get('direction') == "lowest":
                    device.player.volume = 10
                elif slot_dict.get('direction') == "highest":
                    device.player.volume = 100
        return

    def player_sync(self, slot_dict, request_siteid):
        if not slot_dict.get('master') or not slot_dict.get('slave'):
            return "Ich habe nicht beide Orte verstanden."
        err, master_site = self.get_sites(request_siteid, slot_dict, single=True, room_slot='master')
        if err:
            return err
        else:
            master_site = master_site[0]
        err, slave_site = self.get_sites(request_siteid, slot_dict, single=True, room_slot='slave')
        if err or not self.server.connected():
            return err
        else:
            slave_site = slave_site[0]
        master_device = master_site.active_device
        master_device.player.sync(player=slave_site.active_device.player)

    def player_info(self, slot_dict, request_siteid):
        if not self.server.connected():
            return "Der Server kann nicht erreicht werden."
        err, sites = self.get_sites(request_siteid, slot_dict, single=True)
        if err:
            return err
        else:
            site = sites[0]
        device = site.active_device
        if not device or not device.player.connected:
            return "Das gewünschte Gerät ist nicht aktiv."
        artist = device.player.track_artist
        album = device.player.track_album
        title = device.player.track_title
        return f"Gerade wird von {artist} aus {album} der Titel {title} gespielt."

    def queue_next(self, slot_dict, request_siteid):
        err, sites = self.get_sites(request_siteid, slot_dict, single=True)
        if err or not self.server.connected():
            return
        else:
            site = sites[0]
        device = site.active_device
        if device and device.player.connected:
            device.player.next()

    def queue_previous(self, slot_dict, request_siteid):
        err, sites = self.get_sites(request_siteid, slot_dict, single=True)
        if err or not self.server.connected():
            return
        else:
            site = sites[0]
        device = site.active_device
        if device and device.player.connected:
            device.player.prev()

    def queue_restart(self, slot_dict, request_siteid):
        err, sites = self.get_sites(request_siteid, slot_dict, single=True)
        if err or not self.server.connected():
            return
        else:
            site = sites[0]
        device = site.active_device
        if device and device.player.connected:
            device.player.playlist_restart()
