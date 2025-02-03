#!/usr/bin/python3
import json  # added for json status messages
from deezspot.deezloader.dee_api import API
from deezspot.easy_spoty import Spo
from deezspot.deezloader.deegw_api import API_GW
from deezspot.deezloader.deezer_settings import stock_quality
from deezspot.models import (
    Track,
    Album,
    Playlist,
    Preferences,
    Smart,
    Episode,
)
from deezspot.deezloader.__download__ import (
    DW_TRACK,
    DW_ALBUM,
    DW_PLAYLIST,
    DW_EPISODE,
)
from deezspot.exceptions import (
    InvalidLink,
    TrackNotFound,
    NoDataApi,
    AlbumNotFound,
)
from deezspot.libutils.utils import (
    create_zip,
    get_ids,
    link_is_valid,
    what_kind,
)
from deezspot.libutils.others_settings import (
    stock_output,
    stock_recursive_quality,
    stock_recursive_download,
    stock_not_interface,
    stock_zip,
    method_save,
)

Spo()
API()

class DeeLogin:
    def __init__(self, arl=None, email=None, password=None) -> None:
        if arl:
            self.__gw_api = API_GW(arl=arl)
        else:
            self.__gw_api = API_GW(email=email, password=password)

    def download_trackdee(
        self,
        link_track,
        output_dir=stock_output,
        quality_download=stock_quality,
        recursive_quality=stock_recursive_quality,
        recursive_download=stock_recursive_download,
        not_interface=stock_not_interface,
        method_save=method_save,
    ) -> Track:
        link_is_valid(link_track)
        ids = get_ids(link_track)

        try:
            song_metadata = API.tracking(ids)
        except NoDataApi:
            infos = self.__gw_api.get_song_data(ids)
            if "FALLBACK" not in infos:
                raise TrackNotFound(link_track)
            ids = infos["FALLBACK"]["SNG_ID"]
            song_metadata = API.tracking(ids)

        preferences = Preferences()
        preferences.link = link_track
        preferences.song_metadata = song_metadata
        preferences.quality_download = quality_download
        preferences.output_dir = output_dir
        preferences.ids = ids
        preferences.recursive_quality = recursive_quality
        preferences.recursive_download = recursive_download
        preferences.not_interface = not_interface
        preferences.method_save = method_save

        # Determine track details.
        album_name = song_metadata.get("ALB_TITLE") or song_metadata.get("album", "Unknown Album")
        song_name = song_metadata.get("SNG_TITLE") or song_metadata.get("music", "Unknown Song")
        artist_name = song_metadata.get("ART_NAME") or song_metadata.get("artist", "Unknown Artist")

        # Print a JSON status message before starting the download.
        print(
            json.dumps(
                {
                    "status": "downloading",
                    "type": "track",
                    "album": album_name,
                    "song": song_name,
                    "artist": artist_name,
                },
                ensure_ascii=False,
            )
        )

        track = DW_TRACK(preferences).dw()

        # Print a JSON status message once the download is complete.
        print(
            json.dumps(
                {
                    "status": "done",
                    "type": "track",
                    "album": album_name,
                    "song": song_name,
                    "artist": artist_name,
                },
                ensure_ascii=False,
            )
        )

        return track

    def download_albumdee(
        self,
        link_album,
        output_dir=stock_output,
        quality_download=stock_quality,
        recursive_quality=stock_recursive_quality,
        recursive_download=stock_recursive_download,
        not_interface=stock_not_interface,
        make_zip=stock_zip,
        method_save=method_save,
    ) -> Album:
        link_is_valid(link_album)
        ids = get_ids(link_album)

        try:
            album_json = API.get_album(ids)
        except NoDataApi:
            raise AlbumNotFound(link_album)

        # Extract album info for JSON messages
        album_title = album_json.get("title", "Unknown Album")
        album_artist = album_json.get("artist", {}).get("name", "Unknown Artist")
        total_tracks = album_json.get("nb_tracks", 0)

        # Print initializing status
        print(json.dumps({
            "status": "initializing",
            "type": "album",
            "album": album_title,
            "artist": album_artist,
            "total_tracks": total_tracks
        }, ensure_ascii=False))

        # Pre-fetch track metadata to determine progress
        track_ids = [track["id"] for track in album_json.get("tracks", {}).get("data", [])]
        total_tracks = len(track_ids)

        # Simulate progress by iterating over track IDs
        for idx, track_id in enumerate(track_ids, start=1):
            try:
                track_metadata = API.tracking(track_id)
                track_name = track_metadata.get("music", "Unknown Track")
            except NoDataApi:
                track_name = "Unknown Track"

            print(json.dumps({
                "status": "progress",
                "type": "album",
                "track": track_name,
                "current_track": f"{idx}/{total_tracks}",
            }, ensure_ascii=False))

        # Proceed with DW_ALBUM to handle actual download
        song_metadata = API.tracking_album(album_json)

        preferences = Preferences()
        preferences.link = link_album
        preferences.song_metadata = song_metadata
        preferences.quality_download = quality_download
        preferences.output_dir = output_dir
        preferences.ids = ids
        preferences.json_data = album_json
        preferences.recursive_quality = recursive_quality
        preferences.recursive_download = recursive_download
        preferences.not_interface = not_interface
        preferences.method_save = method_save
        preferences.make_zip = make_zip

        album = DW_ALBUM(preferences).dw()

        # Print completion status
        print(json.dumps({
            "status": "done",
            "type": "album",
            "album": album_title,
            "artist": album_artist
        }, ensure_ascii=False))

        return album
    def download_playlistdee(
        self,
        link_playlist,
        output_dir=stock_output,
        quality_download=stock_quality,
        recursive_quality=stock_recursive_quality,
        recursive_download=stock_recursive_download,
        not_interface=stock_not_interface,
        make_zip=stock_zip,
        method_save=method_save,
    ) -> Playlist:
        link_is_valid(link_playlist)
        ids = get_ids(link_playlist)

        playlist_json = API.get_playlist(ids)

        # Extract playlist name and total number of tracks.
        playlist_name = playlist_json.get("name", "Unknown Playlist")
        total_tracks = playlist_json.get("tracks", {}).get(
            "total", len(playlist_json.get("tracks", {}).get("data", []))
        )

        # Print initializing status message for playlist.
        print(
            json.dumps(
                {
                    "status": "initializing",
                    "type": "playlist",
                    "name": playlist_name,
                    "total_tracks": total_tracks,
                },
                ensure_ascii=False,
            )
        )

        tracks_data = playlist_json["tracks"]["data"]
        playlist = Playlist()
        playlist.tracks = []

        for idx, track in enumerate(tracks_data, start=1):
            c_ids = track["id"]
            try:
                c_song_metadata = API.tracking(c_ids)
            except NoDataApi:
                infos = self.__gw_api.get_song_data(c_ids)
                if "FALLBACK" not in infos:
                    # In this fallback case we only have a string.
                    c_song_metadata = {
                        "SNG_TITLE": f"{track['title']} - {track['artist']['name']}"
                    }
                else:
                    c_song_metadata = API.tracking(c_ids)

            track_name = (
                c_song_metadata.get("SNG_TITLE")
                if isinstance(c_song_metadata, dict)
                else track.get("title", "Unknown Track")
            )
            print(
                json.dumps(
                    {
                        "status": "progress",
                        "type": "playlist",
                        "track": track_name,
                        "current_track": f"{idx}/{total_tracks}",
                    },
                    ensure_ascii=False,
                )
            )

            temp_preferences = Preferences()
            temp_preferences.link = link_playlist
            temp_preferences.song_metadata = (
                c_song_metadata if isinstance(c_song_metadata, dict) else {}
            )
            temp_preferences.quality_download = quality_download
            temp_preferences.output_dir = output_dir
            temp_preferences.ids = c_ids
            temp_preferences.recursive_quality = recursive_quality
            temp_preferences.recursive_download = recursive_download
            temp_preferences.not_interface = not_interface
            temp_preferences.method_save = method_save

            track_obj = DW_TRACK(temp_preferences).dw()
            playlist.tracks.append(track_obj)

        if make_zip:
            zip_name = f"{output_dir}playlist {playlist_name}.zip"
            create_zip(playlist.tracks, zip_name=zip_name)
            playlist.zip_path = zip_name

        # Print done message for the playlist.
        print(
            json.dumps(
                {
                    "status": "done",
                    "type": "playlist",
                    "name": playlist_name,
                    "total_tracks": total_tracks,
                },
                ensure_ascii=False,
            )
        )

        return playlist

    def download_artisttopdee(
        self,
        link_artist,
        output_dir=stock_output,
        quality_download=stock_quality,
        recursive_quality=stock_recursive_quality,
        recursive_download=stock_recursive_download,
        not_interface=stock_not_interface,
        method_save=method_save,
    ) -> list[Track]:
        link_is_valid(link_artist)
        ids = get_ids(link_artist)

        playlist_json = API.get_artist_top_tracks(ids)["data"]

        names = [
            self.download_trackdee(
                track["link"],
                output_dir,
                quality_download,
                recursive_quality,
                recursive_download,
                not_interface,
                method_save=method_save,
            )
            for track in playlist_json
        ]

        return names

    def convert_spoty_to_dee_link_track(self, link_track):
        link_is_valid(link_track)
        ids = get_ids(link_track)

        track_json = Spo.get_track(ids)
        external_ids = track_json["external_ids"]

        if not external_ids:
            msg = f"⚠ The track \"{track_json['name']}\" can't be converted to Deezer link :( ⚠"
            raise TrackNotFound(url=link_track, message=msg)

        isrc = f"isrc:{external_ids['isrc']}"
        track_json_dee = API.get_track(isrc)
        track_link_dee = track_json_dee["link"]

        return track_link_dee

    def download_trackspo(
        self,
        link_track,
        output_dir=stock_output,
        quality_download=stock_quality,
        recursive_quality=stock_recursive_quality,
        recursive_download=stock_recursive_download,
        not_interface=stock_not_interface,
        method_save=method_save,
    ) -> Track:
        track_link_dee = self.convert_spoty_to_dee_link_track(link_track)

        # download_trackdee will print its own "downloading" and "done" messages.
        track = self.download_trackdee(
            track_link_dee,
            output_dir=output_dir,
            quality_download=quality_download,
            recursive_quality=recursive_quality,
            recursive_download=recursive_download,
            not_interface=not_interface,
            method_save=method_save,
        )

        return track

    def convert_spoty_to_dee_link_album(self, link_album):
        link_is_valid(link_album)
        ids = get_ids(link_album)
        link_dee = None

        tracks = Spo.get_album(ids)

        try:
            external_ids = tracks["external_ids"]
            if not external_ids:
                raise AlbumNotFound
            upc = f"0{external_ids['upc']}"

            while upc[0] == "0":
                upc = upc[1:]
                try:
                    upc = f"upc:{upc}"
                    url = API.get_album(upc)
                    link_dee = url["link"]
                    break
                except NoDataApi:
                    if upc[0] != "0":
                        raise AlbumNotFound
        except AlbumNotFound:
            tot = tracks["total_tracks"]
            tracks = tracks["tracks"]["items"]
            tot2 = None

            for track in tracks:
                track_link = track["external_urls"]["spotify"]
                track_info = Spo.get_track(track_link)
                try:
                    isrc = f"isrc:{track_info['external_ids']['isrc']}"
                    track_data = API.get_track(isrc)
                    if "id" not in track_data["album"]:
                        continue
                    album_ids = track_data["album"]["id"]
                    album_json = API.get_album(album_ids)
                    tot2 = album_json["nb_tracks"]
                    if tot == tot2:
                        link_dee = album_json["link"]
                        break
                except NoDataApi:
                    pass

            if tot != tot2:
                raise AlbumNotFound(link_album)

        return link_dee

    def download_albumspo(
        self,
        link_album,
        output_dir=stock_output,
        quality_download=stock_quality,
        recursive_quality=stock_recursive_quality,
        recursive_download=stock_recursive_download,
        not_interface=stock_not_interface,
        make_zip=stock_zip,
        method_save=method_save,
    ) -> Album:
        link_dee = self.convert_spoty_to_dee_link_album(link_album)
        album = self.download_albumdee(
            link_dee,
            output_dir,
            quality_download,
            recursive_quality,
            recursive_download,
            not_interface,
            make_zip,
            method_save,
        )
        return album

    def download_playlistspo(
        self,
        link_playlist,
        output_dir=stock_output,
        quality_download=stock_quality,
        recursive_quality=stock_recursive_quality,
        recursive_download=stock_recursive_download,
        not_interface=stock_not_interface,
        make_zip=stock_zip,
        method_save=method_save,
    ) -> Playlist:
        link_is_valid(link_playlist)
        ids = get_ids(link_playlist)

        # Retrieve playlist metadata from Spotify.
        playlist_json = Spo.get_playlist(ids)
        playlist_name = playlist_json.get("name", "Unknown Playlist")
        total_tracks = playlist_json.get("tracks", {}).get(
            "total", len(playlist_json.get("tracks", {}).get("items", []))
        )

        # Print initializing message for the Spotify playlist.
        print(
            json.dumps(
                {
                    "status": "initializing",
                    "type": "playlist",
                    "name": playlist_name,
                    "total_tracks": total_tracks,
                },
                ensure_ascii=False,
            )
        )

        playlist_tracks = playlist_json["tracks"]["items"]
        playlist = Playlist()
        playlist.tracks = []

        for idx, track in enumerate(playlist_tracks, start=1):
            is_track = track.get("track")
            if not is_track:
                continue
            external_urls = is_track.get("external_urls")
            if not external_urls:
                print(f'The track "{is_track.get("name", "Unknown")}" is not available on Spotify :(')
                continue

            # Print intermediate progress message.
            print(
                json.dumps(
                    {
                        "status": "progress",
                        "type": "playlist",
                        "track": is_track.get("name", "Unknown Track"),
                        "current_track": f"{idx}/{total_tracks}",
                    },
                    ensure_ascii=False,
                )
            )

            link_track = external_urls.get("spotify")
            try:
                track_obj = self.download_trackspo(
                    link_track,
                    output_dir=output_dir,
                    quality_download=quality_download,
                    recursive_quality=recursive_quality,
                    recursive_download=recursive_download,
                    not_interface=not_interface,
                    method_save=method_save,
                )
            except (TrackNotFound, NoDataApi):
                info = track["track"]
                artist = info["artists"][0]["name"]
                song = info["name"]
                track_obj = f"{song} - {artist}"
            playlist.tracks.append(track_obj)

        if make_zip:
            zip_name = f"{output_dir}playlist {playlist_name}.zip"
            create_zip(playlist.tracks, zip_name=zip_name)
            playlist.zip_path = zip_name

        # Print done message for the playlist.
        print(
            json.dumps(
                {
                    "status": "done",
                    "type": "playlist",
                    "name": playlist_name,
                    "total_tracks": total_tracks,
                },
                ensure_ascii=False,
            )
        )

        return playlist

    def download_name(
        self,
        artist,
        song,
        output_dir=stock_output,
        quality_download=stock_quality,
        recursive_quality=stock_recursive_quality,
        recursive_download=stock_recursive_download,
        not_interface=stock_not_interface,
        method_save=method_save,
    ) -> Track:
        query = f"track:{song} artist:{artist}"
        search = self.__spo.search(query)
        items = search["tracks"]["items"]

        if len(items) == 0:
            msg = f"No result for {query} :("
            raise TrackNotFound(message=msg)

        link_track = items[0]["external_urls"]["spotify"]

        track = self.download_trackspo(
            link_track,
            output_dir=output_dir,
            quality_download=quality_download,
            recursive_quality=recursive_quality,
            recursive_download=recursive_download,
            not_interface=not_interface,
            method_save=method_save,
        )

        return track

    def download_episode(
        self,
        link_episode,
        output_dir=stock_output,
        quality_download=stock_quality,
        recursive_quality=stock_recursive_quality,
        recursive_download=stock_recursive_download,
        not_interface=stock_not_interface,
        method_save=method_save,
    ) -> Episode:
        link_is_valid(link_episode)
        ids = get_ids(link_episode)

        try:
            episode_metadata = API.tracking(ids)
        except NoDataApi:
            infos = self.__gw_api.get_episode_data(ids)
            if not infos:
                raise TrackNotFound("Episode not found")
            episode_metadata = {
                "music": infos.get("EPISODE_TITLE", ""),
                "artist": infos.get("SHOW_NAME", ""),
                "album": infos.get("SHOW_NAME", ""),
                "date": infos.get("EPISODE_PUBLISHED_TIMESTAMP", "").split()[0],
                "genre": "Podcast",
                "explicit": infos.get("SHOW_IS_EXPLICIT", "2"),
                "disc": 1,
                "track": 1,
                "duration": int(infos.get("DURATION", 0)),
                "isrc": None,
                "image": infos.get("EPISODE_IMAGE_MD5", ""),
            }

        preferences = Preferences()
        preferences.link = link_episode
        preferences.song_metadata = episode_metadata
        preferences.quality_download = quality_download
        preferences.output_dir = output_dir
        preferences.ids = ids
        preferences.recursive_quality = recursive_quality
        preferences.recursive_download = recursive_download
        preferences.not_interface = not_interface
        preferences.method_save = method_save

        episode = DW_EPISODE(preferences).dw()

        return episode

    def download_smart(
        self,
        link,
        output_dir=stock_output,
        quality_download=stock_quality,
        recursive_quality=stock_recursive_quality,
        recursive_download=stock_recursive_download,
        not_interface=stock_not_interface,
        make_zip=stock_zip,
        method_save=method_save,
    ) -> Smart:
        link_is_valid(link)
        link = what_kind(link)
        smart = Smart()

        if "spotify.com" in link:
            source = "https://spotify.com"
        elif "deezer.com" in link:
            source = "https://deezer.com"

        smart.source = source

        if "track/" in link:
            if "spotify.com" in link:
                func = self.download_trackspo
            elif "deezer.com" in link:
                func = self.download_trackdee
            else:
                raise InvalidLink(link)

            track = func(
                link,
                output_dir=output_dir,
                quality_download=quality_download,
                recursive_quality=recursive_quality,
                recursive_download=recursive_download,
                not_interface=not_interface,
                method_save=method_save,
            )
            smart.type = "track"
            smart.track = track

        elif "album/" in link:
            if "spotify.com" in link:
                func = self.download_albumspo
            elif "deezer.com" in link:
                func = self.download_albumdee
            else:
                raise InvalidLink(link)

            album = func(
                link,
                output_dir=output_dir,
                quality_download=quality_download,
                recursive_quality=recursive_quality,
                recursive_download=recursive_download,
                not_interface=not_interface,
                make_zip=make_zip,
                method_save=method_save,
            )
            smart.type = "album"
            smart.album = album

        elif "playlist/" in link:
            if "spotify.com" in link:
                func = self.download_playlistspo
            elif "deezer.com" in link:
                func = self.download_playlistdee
            else:
                raise InvalidLink(link)

            playlist = func(
                link,
                output_dir=output_dir,
                quality_download=quality_download,
                recursive_quality=recursive_quality,
                recursive_download=recursive_download,
                not_interface=not_interface,
                make_zip=make_zip,
                method_save=method_save,
            )
            smart.type = "playlist"
            smart.playlist = playlist

        return smart
