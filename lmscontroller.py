import LMSTools
import json
import re
import random
from typing import Callable


class Device:
    def __init__(self, player):
        self.name = player.name
        self.site_id = str()
        self.names_list = [player.name]
        self.synonyms = list()
        self.bluetooth = dict()
        self.soundcard = str()
        self.player = player
        self.auto_pause = False
        self.on_the_fly = False


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
            if not self.devices_dict.get(device_dict['squeezelite_mac']):
                player = LMSTools.LMSPlayer(device_dict['squeezelite_mac'], server, False, device_dict['name'])
                self.devices_dict[device_dict['squeezelite_mac']] = Device(player)

            device = self.devices_dict[device_dict['squeezelite_mac']]
            device.name = device_dict['name']
            device.site_id = self.site_id
            device.names_list = device_dict['names_list']
            device.synonyms = device_dict['synonyms']
            device.bluetooth = device_dict['bluetooth']
            device.soundcard = device_dict['soundcard']


class LMSController:
    def __init__(self, mqtt_client, lms_host, lms_port, lms_username, lms_password):
        self.mqtt_client = mqtt_client
        self.server = LMSTools.LMSServer(lms_host, lms_port, lms_username, lms_password)
        self.sites_dict = dict()
        self.pending_actions = dict()
        self.current_status = dict()
        self.inject_siteids_dict = dict()

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
            nosite_devices = self.nosite_players_dict
            for d in nosite_devices.keys():
                if d not in devices:
                    devices.append(d)
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
        if not slot_dict or not slot_dict.get(room_slot):
            room_slot_value = "hier"
        else:
            room_slot_value = slot_dict.get(room_slot)

        if room_slot_value == "hier" and self.sites_dict.get(request_siteid):
            sites = [self.sites_dict[request_siteid]]
        elif room_slot_value == "hier" and not self.sites_dict.get(request_siteid):
            sites = []
        elif room_slot_value == "alle":
            sites = [self.sites_dict[siteid] for siteid in self.sites_dict]
        else:
            sites = [self.sites_dict[siteid] for siteid in self.sites_dict
                     if self.sites_dict[siteid].room_name == room_slot_value]

        if not sites and room_slot_value == "alle":
            return "Es wurden noch keine Räume konfiguriert.", None
        elif not sites and room_slot_value != "alle":
            return f"Der Raum {room_slot_value} wurde noch nicht konfiguriert.", None
        if single and len(sites) > 1:
            return "Für diese Funktion darf nur ein einziger Raum genannt werden.", None

        if not slot_dict or not slot_dict.get('area'):
            area_slot_value = "in diesem Bereich"
        else:
            area_slot_value = slot_dict.get('area')

        if area_slot_value == "in diesem Bereich" and self.sites_dict.get(request_siteid):
            sites = [site for site in sites if site.area == self.sites_dict[request_siteid].area]
        elif area_slot_value == "in diesem Bereich" and not self.sites_dict.get(request_siteid):
            return "Der Raum hier wurde noch nicht konfiguriert.", None
        elif area_slot_value == "in allen Bereichen" and not slot_dict.get(room_slot):
            sites = [self.sites_dict[siteid] for siteid in self.sites_dict]
        elif not slot_dict.get(room_slot):
            sites = [self.sites_dict[siteid] for siteid in self.sites_dict
                     if self.sites_dict[siteid].area == area_slot_value]
        else:
            sites = [site for site in sites if site.area == self.sites_dict[site.site_id].area]
        if not sites:
            return "Diese Auswahl an Räumen existiert nicht.", None
        return None, sites

    @property
    def nosite_players_dict(self):
        """
        Get the LMSplayers which are not configured in a site.
        :rtype: dict
        :return: dictionary of on-the-fly LMSplayer objects
        """
        if self.server.connected:
            players_dict = {player.ref: player for player in self.server.get_players() if player.connected}
            for site_id in self.sites_dict:
                site = self.sites_dict[site_id]
                for device_mac in site.devices_dict:
                    device = site.devices_dict[device_mac]
                    if device.player.ref in players_dict:
                        del players_dict[device.player.ref]
            players = {players_dict[ref].name: players_dict[ref] for ref in players_dict}
        else:
            players = dict()
        print("Found on-the-fly players: ", str(players.keys()))
        return players

    def make_devices_ready(self, slots: dict, request_siteid: str, target: Callable = None, args: tuple = (),
                           sites: list = None):
        """
        Prepare devices for playing. Connect bluetooth devices and start squeezelite
        if necessary with queues. Then call the target function if given.
        :param slots: Slot dictionary from Snips
        :param request_siteid: siteId of the request site from Snips
        :param target: Target function which should be called after successfull setup
        :param args: Arguments which the target function will be called with
        :param sites: Optional list of sites. Useful for synchronisation
        :return: errors or result as str
        """
        if not self.server.connected:
            return "Es konnte keine Verbindung zum Medienserver hergestellt werden."

        request_site = self.sites_dict.get(request_siteid)
        if not request_site:
            return "Dieser Raum hier wurde noch nicht konfiguriert."

        if not sites:
            err, sites = self.get_sites(request_siteid, slots)
            if err:
                return err

        if not request_site.action_target:
            request_site.need_connection_queue = list()
            request_site.need_service_queue = list()

            if sites:
                nosite_players = self.nosite_players_dict
                for site in sites:
                    if site.active_device and not slots.get('device'):
                        # device is the current active device of site if there is any and slot is filled
                        device = site.active_device
                    else:
                        if slots.get('device') == "alle":
                            return "Es geht nur ein Gerät pro Raum."
                        elif slots.get('device'):
                            device_slot_value = slots['device']
                        else:
                            device_slot_value = site.default_device_name
                        found = [site.devices_dict[mac] for mac in site.devices_dict
                                 if device_slot_value in site.devices_dict[mac].names_list]
                        if not found:
                            player = nosite_players.get(device_slot_value)
                            if player:
                                # If LMSplayer with this name exists, add on-the-fly device to site
                                # It will be deleted if it is needed again but disconnected
                                device = Device(player)
                                device.site_id = site.site_id
                                device.on_the_fly = True
                                site.devices_dict[player.ref] = device
                            else:
                                return f"Dieses Gerät gibt es im Raum {site.room_name} nicht."
                        else:
                            device = found[0]

                        if site.active_device and site.active_device != device:
                            site.active_device.player.pause()
                            site.active_device.auto_pause = False

                    # Check bluetooth connection if device is bluetooth device
                    if device.bluetooth and not device.bluetooth['is_connected']:
                        request_site.need_connection_queue.append(device)

                    # Check LMSplayer connection
                    if device.player.connected:
                        # Set active device of site to that device
                        site.active_device = device
                    else:
                        if device.soundcard:
                            # If device has ALSA soundcard, append it to the squeezelite_start queue
                            # The active device of site will be set after connecting successfully
                            request_site.need_service_queue.append(device)
                        else:
                            if device.on_the_fly:
                                # Delete disconnected on-the-fly LMSplayer and its device from site
                                del site.devices_dict[device.player.ref]
                                site.active_device = None
                                if len(sites) > 1:
                                    continue
                            return f"Das Gerät {device.name} ist nicht mit dem Medienserver verbunden."

            # Set action target function which will be called if bluetooth
            # connection queue and squeezelite_start queue are empty
            request_site.action_target = target
            request_site.action_target_args = args

        if request_site.need_connection_queue:
            for device in request_site.need_connection_queue:
                site = self.sites_dict[device.site_id]
                site.pending_action = {
                    'slot_dict': slots,
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
                    'slot_dict': slots,
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
                    'squeeze_mac': device.player.ref,
                    'soundcard': device.soundcard,
                    'player_name': client_name,
                    'device_name': device.name,
                }
                self.mqtt_client.publish(
                    f'squeezebox/request/oneSite/{site.site_id}/serviceStart',
                    json.dumps(payload)
                )
            return None

        if request_site.action_target:  # Call target function after all queues
            result = request_site.action_target(*request_site.action_target_args)
            request_site.action_target = None
            request_site.action_target_args = None
            return result

    def get_player_and_sync(self, slot_dict, request_siteid):
        """
        Returns one LMSplayer object and syncs this player to others if in slots
        :param slot_dict: Slot dictionary from Snips
        :param request_siteid: siteId of the request site from Snips
        :return: error, player
        """
        err, sites = self.get_sites(request_siteid, slot_dict)
        if err:
            return err, None

        if len(sites) > 1:
            err, request_site = self.get_sites(request_siteid)
            if err:
                return err, None
            request_site = request_site[0]
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
        if not podcast_name:
            return "Es wurde kein Podcast Name gesagt."

        found_podcasts = list()
        count = self.server.request(params="favorites items").get('count')
        if count:
            favorite_dicts = self.server.request(params=f"favorites items 0 {count}")['loop_loop']
            music_albums = self.get_music_albums()
            music_artists = self.get_music_artists()
            for favorite_dict in favorite_dicts:
                name = favorite_dict['name']
                if name not in found_podcasts and favorite_dict['hasitems'] \
                        and name not in music_albums and name not in music_artists and name == podcast_name:
                    found_podcasts.append(favorite_dict)
                    break

        if found_podcasts:
            # Play podcast from favorites
            result_type = "favorites"
            podcast_id = found_podcasts[0].get('id')
            result = player.request(f"favorites items 0 30 item_id:{podcast_id}.0")
            if not result.get('count'):
                return "Es gibt keine Episoden von diesem Podcast."
            found_episodes = [item_dict for item_dict in result.get('loop_loop') if item_dict.get('isaudio')]
            if not found_episodes:
                return "Es gibt keine Audio Episoden zu diesem Podcast."
        else:
            # Search for podcast in the web
            result_type = "podcast"
            result = player.request(f"search items 0 30 search:{'+'.join(podcast_name.split(' '))}")
            if result.get('count'):
                found_podcasts = [item_dict for item_dict in result.get('loop_loop')
                                  if item_dict.get('hasitems')]
            if not found_podcasts:
                return "Es gibt keinen solchen Podcast."

            podcast_id = found_podcasts[0].get('id')
            result = player.request(f"search items 0 50 item_id:{podcast_id}.0")
            if not result.get('count'):
                return "Es gibt keine Episoden von diesem Podcast."
            found_episodes = [item_dict for item_dict in result.get('loop_loop') if item_dict.get('isaudio')]
            if not found_episodes:
                return "Es gibt keine Audio Episoden zu diesem Podcast."

        if not slot_dict.get('index') and not slot_dict.get('count'):
            episode_ids = [found_episodes[0].get('id')]
        else:
            index = slot_dict.get('index')
            count = slot_dict.get('count')
            if index and index > len(found_episodes) or count and count > len(found_episodes):
                return "Es gibt nicht so viele Episoden in diesem Podcast."
            if index:
                episode_ids = [found_episodes[index - 1].get('id')]
            else:
                episode_ids = [episode.get('id') for episode in found_episodes[:count]]
        for episode_id in episode_ids:
            if episode_id == episode_ids[0]:
                player.request(f"{result_type} playlist play item_id:{episode_id}")
            else:
                player.request(f"{result_type} playlist add item_id:{episode_id}")

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

    def player_sync_step1(self, slot_dict, request_siteid):
        if not slot_dict.get('master') or not slot_dict.get('slave'):
            return "Ich habe nicht beide Orte verstanden."
        err, master_site = self.get_sites(request_siteid, slot_dict, single=True, room_slot='master')
        if err:
            return err
        else:
            master_site = master_site[0]
        err, slave_site = self.get_sites(request_siteid, slot_dict, single=True, room_slot='slave')
        if err:
            return err
        elif not self.server.connected():
            return "Der Server kann nicht erreicht werden."
        else:
            slave_site = slave_site[0]
        self.make_devices_ready(slot_dict, request_siteid, target=self.player_sync_step2,
                                args=(master_site, slave_site,), sites=[master_site, slave_site])
        return None

    @staticmethod
    def player_sync_step2(master_site, slave_site):
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
