#!/usr/bin/python3

from spotipy import Spotify
from deezspot.exceptions import InvalidLink
from spotipy.exceptions import SpotifyException
from spotipy_anon import SpotifyAnon

class Spo:
    __error_codes = [404, 400]

    @classmethod
    def __init__(cls):
        cls.__api = Spotify(
            auth_manager=SpotifyAnon()  # Instead using spotipy client use spotify anon because spotify client can't fetch information from track or playlist from official spotify
        )

    @classmethod
    def __lazy(cls, results):
        albums = results['items']

        while results['next']:
            results = cls.__api.next(results)
            albums.extend(results['items'])

        return results

    @classmethod
    def get_track(cls, ids):
        try:
            track_json = cls.__api.track(ids)
        except SpotifyException as error:
            if error.http_status in cls.__error_codes:
                raise InvalidLink(ids)

        return track_json

    @classmethod
    def get_album(cls, ids):
        try:
            album_json = cls.__api.album(ids)
        except SpotifyException as error:
            if error.http_status in cls.__error_codes:
                raise InvalidLink(ids)

        tracks = album_json['tracks']
        cls.__lazy(tracks)

        return album_json

    @classmethod
    def get_playlist(cls, ids):
        try:
            playlist_json = cls.__api.playlist(ids)
        except SpotifyException as error:
            if error.http_status in cls.__error_codes:
                raise InvalidLink(ids)

        tracks = playlist_json['tracks']
        cls.__lazy(tracks)

        return playlist_json

    @classmethod
    def get_episode(cls, ids):
        try:
            episode_json = cls.__api.episode(ids)
        except SpotifyException as error:
            if error.http_status in cls.__error_codes:
                raise InvalidLink(ids)

        return episode_json

    @classmethod
    def search(cls, query, search_type='track', limit=10):
        search = cls.__api.search(q=query, type=search_type, limit=limit)
        return search

    @classmethod
    def get_artist(cls, ids, album_type='album,single,compilation,appears_on', limit=50):
        try:
            # Request all types of releases by the artist.
            discography = cls.__api.artist_albums(
                ids,
                album_type=album_type,
                limit=limit
            )
        except SpotifyException as error:
            if error.http_status in cls.__error_codes:
                raise InvalidLink(ids)
            else:
                raise

        # Ensure that all pages of results are fetched.
        cls.__lazy(discography)
        return discography
