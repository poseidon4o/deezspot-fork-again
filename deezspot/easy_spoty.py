#!/usr/bin/python3

from spotipy import Spotify
from deezspot.exceptions import InvalidLink
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials
import os

class Spo:
    __error_codes = [404, 400]
    
    # Class-level API instance to store the last used API client
    __api = None

    @classmethod
    def __init__(cls, client_id, client_secret):
        """
        Initialize the Spotify API client.
        
        Args:
            client_id (str): Spotify API client ID.
            client_secret (str): Spotify API client secret.
        """
        if not client_id or not client_secret:
            raise ValueError("Spotify API credentials required. Provide client_id and client_secret.")
            
        client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        
        cls.__api = Spotify(
            auth_manager=client_credentials_manager
        )

    @classmethod
    def __get_api(cls, client_id, client_secret):
        """
        Get a Spotify API instance with the provided credentials.
        
        Args:
            client_id (str): Spotify API client ID
            client_secret (str): Spotify API client secret
            
        Returns:
            A Spotify API instance
        """
        # Create a new API instance with the provided credentials
        client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        return Spotify(auth_manager=client_credentials_manager)

    @classmethod
    def __lazy(cls, results, api):
        """Process paginated results"""
        albums = results['items']

        while results['next']:
            results = api.next(results)
            albums.extend(results['items'])

        return results

    @classmethod
    def get_track(cls, ids, client_id, client_secret):
        """
        Get track information by ID.
        
        Args:
            ids (str): Spotify track ID
            client_id (str): Spotify client ID
            client_secret (str): Spotify client secret
            
        Returns:
            dict: Track information
        """
        api = cls.__get_api(client_id, client_secret)
        try:
            track_json = api.track(ids)
        except SpotifyException as error:
            if error.http_status in cls.__error_codes:
                raise InvalidLink(ids)

        return track_json

    @classmethod
    def get_album(cls, ids, client_id, client_secret):
        """
        Get album information by ID.
        
        Args:
            ids (str): Spotify album ID
            client_id (str): Spotify client ID
            client_secret (str): Spotify client secret
            
        Returns:
            dict: Album information
        """
        api = cls.__get_api(client_id, client_secret)
        try:
            album_json = api.album(ids)
        except SpotifyException as error:
            if error.http_status in cls.__error_codes:
                raise InvalidLink(ids)

        tracks = album_json['tracks']
        cls.__lazy(tracks, api)

        return album_json

    @classmethod
    def get_playlist(cls, ids, client_id, client_secret):
        """
        Get playlist information by ID.
        
        Args:
            ids (str): Spotify playlist ID
            client_id (str): Spotify client ID
            client_secret (str): Spotify client secret
            
        Returns:
            dict: Playlist information
        """
        api = cls.__get_api(client_id, client_secret)
        try:
            playlist_json = api.playlist(ids)
        except SpotifyException as error:
            if error.http_status in cls.__error_codes:
                raise InvalidLink(ids)

        tracks = playlist_json['tracks']
        cls.__lazy(tracks, api)

        return playlist_json

    @classmethod
    def get_episode(cls, ids, client_id, client_secret):
        """
        Get episode information by ID.
        
        Args:
            ids (str): Spotify episode ID
            client_id (str): Spotify client ID
            client_secret (str): Spotify client secret
            
        Returns:
            dict: Episode information
        """
        api = cls.__get_api(client_id, client_secret)
        try:
            episode_json = api.episode(ids)
        except SpotifyException as error:
            if error.http_status in cls.__error_codes:
                raise InvalidLink(ids)

        return episode_json

    @classmethod
    def search(cls, query, search_type='track', limit=10, client_id=None, client_secret=None):
        """
        Search for tracks, albums, artists, or playlists.
        
        Args:
            query (str): Search query
            search_type (str, optional): Type of search ('track', 'album', 'artist', 'playlist')
            limit (int, optional): Maximum number of results to return
            client_id (str): Spotify client ID
            client_secret (str): Spotify client secret
            
        Returns:
            dict: Search results
        """
        if not client_id or not client_secret:
            raise ValueError("Spotify API credentials required. Provide client_id and client_secret.")
            
        api = cls.__get_api(client_id, client_secret)
        search = api.search(q=query, type=search_type, limit=limit)
        return search

    @classmethod
    def get_artist(cls, ids, client_id, client_secret, album_type='album,single,compilation,appears_on', limit=50):
        """
        Get artist information and discography by ID.
        
        Args:
            ids (str): Spotify artist ID
            client_id (str): Spotify client ID
            client_secret (str): Spotify client secret
            album_type (str, optional): Types of albums to include
            limit (int, optional): Maximum number of results
            
        Returns:
            dict: Artist discography
        """
        api = cls.__get_api(client_id, client_secret)
        try:
            # Request all types of releases by the artist.
            discography = api.artist_albums(
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
        cls.__lazy(discography, api)
        return discography
