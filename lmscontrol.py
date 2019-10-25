import LMSTools
import requests
import re


class LMSController:
    def __init__(self, lms_host, lms_port):
        self.lmserver = LMSTools.server.LMSServer(lms_host, lms_port)

    def get_music_names(self):
        try:
            all_titles = list()
            titles = self.lmserver.request(params="titles list")
            if titles.get('count') >= 1:
                for title_dict in titles.get('titles_loop'):
                    title = title_dict['title']
                    if title not in all_titles:
                        all_titles.append(title)

            all_albums = list()
            albums = self.lmserver.request(params="albums list")
            if albums.get('count') >= 1:
                for album_dict in albums.get('albums_loop'):
                    album = album_dict['album']
                    if album not in all_albums:
                        all_albums.append(album)

            all_artists = list()
            artists = self.lmserver.request(params="artists list")
            if artists.get('count') >= 1:
                for artist_dict in artists.get('artists_loop'):
                    for artist in re.split(r'; |;|, |,', artist_dict['artist']):
                        if artist and artist not in all_artists:
                            all_artists.append(artist)

            all_genres = list()
            genres = self.lmserver.request(params="genres list")
            if genres.get('count') >= 1:
                for genre_dict in genres.get('genres_loop'):
                    for genre in re.split(r'; |;|, |,|/| / ', genre_dict['genre']):
                        if genre and genre not in all_genres:
                            all_genres.append(genre)

            all_playlists = list()
            playlists = self.lmserver.request(params="playlists list")
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

    def search_music(self, term, start, end):
        try:
            found_items = self.lmserver.request(params=f"search {start} {end} term:{term}")
            return False, found_items

        except requests.exceptions.ConnectionError:
            return True, None
