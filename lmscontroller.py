import LMSTools
import requests
import json
import re


class LMSController:
    def __init__(self, mqtt_client, lms_host, lms_port):
        self.mqtt_client = mqtt_client
        self.server = LMSTools.LMSServer(lms_host, lms_port)
        self.sites_info = dict()
        self.pending_actions = dict()
        self.auto_paused = dict()

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

    def get_site_info(self, slot_dict, request_siteid):
        site_info = {'room_name': None, 'site_id': None}
        err = None
        if 'room' in slot_dict:
            if request_siteid in self.sites_info and \
                    slot_dict['room'] == self.sites_info[request_siteid]['room_name'] \
                    or slot_dict['room'] == "hier":
                site_info['site_id'] = request_siteid
            elif request_siteid in self.sites_info and \
                    slot_dict['room'] != self.sites_info[request_siteid]['room_name']:
                dict_rooms = {self.sites_info[siteid]['room_name']: siteid for siteid in self.sites_info}
                site_info['site_id'] = dict_rooms[slot_dict['room']]
            else:
                err = f"Der Raum {slot_dict['room']} wurde noch nicht konfiguriert."
        else:
            site_info['site_id'] = request_siteid

        if site_info['site_id'] in self.sites_info and 'room_name' in self.sites_info[site_info['site_id']]:
            site_info['room_name'] = self.sites_info[site_info['site_id']]['room_name']
        elif 'room' in slot_dict:
            err = f"Der Raum {slot_dict['room']} wurde noch nicht konfiguriert."
        else:
            err = "Es gab einen Fehler."
        return err, site_info

    def get_player(self, site_info):
        player = self.server.get_player_from_name(site_info['room_name'])
        if player:
            return None, player
        else:
            return "Dieses Gerät gibt es nicht.", None

    def new_music(self, slot_dict, request_siteid, pending_action=None):

        err, site_info = self.get_site_info(slot_dict, request_siteid)
        if err:
            return err

        if not pending_action:
            if 'device' in slot_dict:
                found = [d['bluetooth']['addr'] for d in site_info['devices']
                         if slot_dict['device'] in d['names_list']]
                if not found:
                    return "Dieses Gerät gibt es nicht."
                else:
                    addr = found[0]
            else:
                found = [d['bluetooth']['addr'] for d in site_info['devices']
                         if d['name'] == site_info['default_device']]
                addr = found[0]
            self.pending_actions[site_info['site_id']] = {'pending_action': "new_music",
                                                          'slot_dict': slot_dict,
                                                          'request_siteid': request_siteid}
            self.mqtt_client.publish(f'bluetooth/request/oneSite/{site_info["site_id"]}/deviceConnect',
                                     json.dumps({'addr': addr}))
            return None
        else:
            del self.pending_actions[site_info['site_id']]

        err, player = self.get_player(site_info)
        if err:
            return err
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
        err, site_info = self.get_site_info(slot_dict, request_siteid)
        if err:
            return
        err, player = self.get_player(site_info)
        if err:
            return
        try:
            player.pause()
        except requests.exceptions.ConnectionError:
            pass
        return

    def play_music(self, slot_dict, request_siteid):
        err, site_info = self.get_site_info(slot_dict, request_siteid)
        if err:
            return
        err, player = self.get_player(site_info)
        if err:
            return
        try:
            player.play(0.5)
        except requests.exceptions.ConnectionError:
            pass
        return
