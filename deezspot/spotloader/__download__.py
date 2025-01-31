import traceback
import json
import os 
import time
from copy import deepcopy
from os.path import isfile, dirname
from librespot.core import Session
from deezspot.exceptions import TrackNotFound
from librespot.metadata import TrackId, EpisodeId
from deezspot.spotloader.spotify_settings import qualities
from deezspot.libutils.others_settings import answers
from deezspot.__taggers__ import write_tags, check_track
from librespot.audio.decoders import AudioQuality, VorbisOnlyAudioQuality
from os import (
    remove,
    system,
    replace as os_replace,
)
from deezspot.models import (
    Track,
    Album,
    Playlist,
    Preferences,
    Episode,
)
from deezspot.libutils.utils import (
    set_path,
    create_zip,
    request,
)
import mutagen  # Added import for metadata handling

class Download_JOB:
    session = None

    @classmethod
    def __init__(cls, session: Session) -> None:
        cls.session = session

class EASY_DW:
    def __init__(
        self,
        preferences: Preferences
    ) -> None:
        self.__ids = preferences.ids
        self.__link = preferences.link
        self.__output_dir = preferences.output_dir
        self.__method_save = preferences.method_save
        self.__song_metadata = preferences.song_metadata
        self.__not_interface = preferences.not_interface
        self.__quality_download = preferences.quality_download or "NORMAL"
        self.__recursive_download = preferences.recursive_download
        self.__type = "episode" if preferences.is_episode else "track"

        self.__c_quality = qualities[self.__quality_download]
        self.__fallback_ids = self.__ids

        self.__set_quality()
        if preferences.is_episode:
            self.__write_episode()
        else:
            self.__write_track()

    def __set_quality(self) -> None:
        self.__dw_quality = self.__c_quality['n_quality']
        self.__file_format = self.__c_quality['f_format']
        self.__song_quality = self.__c_quality['s_quality']

    def __set_song_path(self) -> None:
        self.__song_path = set_path(
            self.__song_metadata,
            self.__output_dir,
            self.__song_quality,
            self.__file_format,
            self.__method_save
        )

    def __set_episode_path(self) -> None:
        self.__song_path = set_path(
            self.__song_metadata,
            self.__output_dir,
            self.__song_quality,
            self.__file_format,
            self.__method_save,
            is_episode=True
        )

    def __write_track(self) -> None:
        self.__set_song_path()

        self.__c_track = Track(
            self.__song_metadata, self.__song_path,
            self.__file_format, self.__song_quality,
            self.__link, self.__ids
        )

        self.__c_track.md5_image = self.__ids
        self.__c_track.set_fallback_ids(self.__fallback_ids)

    def __write_episode(self) -> None:
        self.__set_episode_path()

        self.__c_episode = Episode(
            self.__song_metadata, self.__song_path,
            self.__file_format, self.__song_quality,
            self.__link, self.__ids
        )

        self.__c_episode.md5_image = self.__ids
        self.__c_episode.set_fallback_ids(self.__fallback_ids)

    def __convert_audio(self) -> None:
        temp_filename = self.__song_path.replace(".ogg", ".tmp")
        os_replace(self.__song_path, temp_filename)
        ffmpeg_cmd = f"ffmpeg -y -hide_banner -loglevel error -i \"{temp_filename}\" -c:a copy \"{self.__song_path}\""
        system(ffmpeg_cmd)
        remove(temp_filename)

    def __track_exists(self) -> bool:
        """Check if a track with the same title and album exists in the destination directory."""
        if self.__type != 'track':
            return False  # Skip check for episodes

        current_title = self.__song_metadata.get('music', '')
        current_album = self.__song_metadata.get('album', '')
        
        if not current_title or not current_album:
            return False

        for root, _, files in os.walk(self.__output_dir):
            for file in files:
                if file.lower().endswith(('.mp3', '.flac', '.ogg', '.m4a', '.wav')):
                    file_path = os.path.join(root, file)
                    try:
                        audio = mutagen.File(file_path, easy=True)
                        if not audio:
                            continue
                        title = audio.get('title', [None])[0]
                        album = audio.get('album', [None])[0]
                        if title and album and title.lower() == current_title.lower() and album.lower() == current_album.lower():
                            return True
                    except Exception:
                        continue
        return False

    def get_no_dw_track(self) -> Track:
        return self.__c_track

    def easy_dw(self) -> Track:
        pic = self.__song_metadata['image']
        image = request(pic).content
        self.__song_metadata['image'] = image
        song = f"{self.__song_metadata['music']} - {self.__song_metadata['artist']}"

        # Check if track already exists
        if self.__track_exists():
            print(json.dumps({
                "status": "skipped",
                "type": self.__type,
                "album": self.__song_metadata['album'],
                "song": self.__song_metadata['music'],
                "artist": self.__song_metadata['artist'],
            }))
            skipped_track = Track(
                self.__song_metadata,
                None, None,
                None, None, None,
            )
            skipped_track.success = False
            return skipped_track

        # Add initial download status
        print(json.dumps({
            "status": "downloading",
            "type": self.__type,
            "album": self.__song_metadata['album'],
            "song": self.__song_metadata['music'],
            "artist": self.__song_metadata['artist']
        }))

        try:
            self.download_try()
        except Exception as e:
            traceback.print_exc()
            raise e

        return self.__c_track

    def download_try(self) -> Track:
        song = f"{self.__song_metadata['music']} - {self.__song_metadata['artist']}"
        track_id = self.__ids
        max_retries = 10
        retry_delay = 30
        retries = 0

        try:
            # Existing file check (retained for specific path check)
            if isfile(self.__song_path) and check_track(self.__c_track):
                if self.__recursive_download:
                    return self.__c_track

                ans = input(f'Track "{self.__song_path}" already exists, do you want to redownload it?(y or n):')
                if ans.lower() not in ('y', 'yes'):
                    return self.__c_track

            while True:
                try:
                    track_id_obj = TrackId.from_base62(self.__ids)
                    stream = Download_JOB.session.content_feeder().load_track(
                        track_id_obj,
                        VorbisOnlyAudioQuality(self.__dw_quality),
                        False,
                        None
                    )

                    total_size = stream.input_stream.size
                    os.makedirs(dirname(self.__song_path), exist_ok=True)

                    with open(self.__song_path, "wb") as f:
                        c_stream = stream.input_stream.stream()
                        data = c_stream.read(total_size)
                        c_stream.close()
                        f.write(data)

                    break

                except RuntimeError as e:
                    if "Failed fetching audio key!" in str(e) and retries < max_retries:
                        print(json.dumps({
                            "status": "retrying",
                            "max_retries": max_retries,
                            "retries": retries + 1,
                            "seconds_left": retry_delay,
                            "song": self.__song_metadata['music'],
                            "artist": self.__song_metadata['artist'],
                            "album": self.__song_metadata['album']
                        }))
                        time.sleep(retry_delay)
                        retries += 1
                    else:
                        raise

            self.__convert_audio()
            self.__write_track()
            write_tags(self.__c_track)

            print(json.dumps({
                "status": "done",
                "type": self.__type,
                "album": self.__song_metadata['album'],
                "song": self.__song_metadata['music'],
                "artist": self.__song_metadata['artist']
            }))
            return self.__c_track

        except Exception as e:
            print(f"Error downloading {song}: {str(e)}")
            raise e

    def download_eps(self) -> Episode:
        if isfile(self.__song_path) and check_track(self.__c_episode):
            if self.__recursive_download:
                return self.__c_episode

            ans = input(
                f"Episode \"{self.__song_path}\" already exists, do you want to redownload it?(y or n):"
            )

            if not ans in answers:
                return self.__c_episode

        # Add episode start status
        print(json.dumps({
            "status": "downloading",
            "type": "episode",
            "album": self.__song_metadata['album'],
            "song": self.__song_metadata['music'],
            "artist": self.__song_metadata['artist']
        }))

        episode_id = EpisodeId.from_base62(self.__ids)

        try:
            stream = Download_JOB.session.content_feeder().load_episode(
                episode_id,
                AudioQuality(self.__dw_quality),
                False,
                None
            )
        except RuntimeError:
            raise TrackNotFound(self.__link)

        total_size = stream.input_stream.size

        os.makedirs(dirname(self.__song_path), exist_ok=True)

        with open(self.__song_path, "wb") as f:
            c_stream = stream.input_stream.stream()
            data = c_stream.read(total_size)
            c_stream.close()
            f.write(data)

        self.__convert_audio()
        self.__write_episode()
        write_tags(self.__c_episode)

        # Add episode completion status
        print(json.dumps({
            "status": "done",
            "type": "episode",
            "album": self.__song_metadata['album'],
            "song": self.__song_metadata['music'],
            "artist": self.__song_metadata['artist']
        }))

        return self.__c_episode

def download_cli(preferences: Preferences) -> None:
    __link = preferences.link
    __output_dir = preferences.output_dir
    __method_save = preferences.method_save
    __not_interface = preferences.not_interface
    __quality_download = preferences.quality_download
    __recursive_download = preferences.recursive_download
    __recursive_quality = preferences.recursive_quality

    cmd = f"deez-dw.py -so spo -l \"{__link}\" "

    if __output_dir:
        cmd += f"-o {__output_dir} "
    if __method_save:
        cmd += f"-sa {__method_save} "
    if __not_interface:
        cmd += f"-g "
    if __quality_download:
        cmd += f"-q {__quality_download} "
    if __recursive_download:
        cmd += f"-rd "
    if __recursive_quality:
        cmd += f"-rq"

    system(cmd)

class DW_TRACK:
    def __init__(
        self,
        preferences: Preferences
    ) -> None:

        self.__preferences = preferences

    def dw(self) -> Track:
        track = EASY_DW(self.__preferences).easy_dw()

        return track

    def dw2(self) -> Track:
        track = EASY_DW(self.__preferences).get_no_dw_track()
        download_cli(self.__preferences)

        return track

class DW_ALBUM:
    def __init__(
        self,
        preferences: Preferences
    ) -> None:

        self.__preferences = preferences
        self.__ids = self.__preferences.ids
        self.__make_zip = self.__preferences.make_zip
        self.__output_dir = self.__preferences.output_dir
        self.__method_save = self.__preferences.method_save
        self.__song_metadata = self.__preferences.song_metadata
        self.__not_interface = self.__preferences.not_interface

        self.__song_metadata_items = self.__song_metadata.items()

    def dw(self) -> Album:
        pic = self.__song_metadata['image']
        image = request(pic).content
        self.__song_metadata['image'] = image

        album = Album(self.__ids)
        album.image = image
        album.nb_tracks = self.__song_metadata['nb_tracks']
        album.album_name = self.__song_metadata['album']
        album.upc = self.__song_metadata['upc']
        tracks = album.tracks
        album.md5_image = self.__ids
        album.tags = self.__song_metadata

        # Print initializing status
        print(json.dumps({
            "status": "initializing",
            "type": "album",
            "album": self.__song_metadata['album'],
            "artist": self.__song_metadata['artist']
        }))

        c_song_metadata = {}

        for key, item in self.__song_metadata_items:
            if type(item) is not list:
                c_song_metadata[key] = self.__song_metadata[key]

        for a in range(album.nb_tracks):  # Replaced tqdm loop with regular loop
            for key, item in self.__song_metadata_items:
                if type(item) is list:
                    c_song_metadata[key] = self.__song_metadata[key][a]

            song_name = c_song_metadata['music']
            artist_name = c_song_metadata['artist']
            album_name = c_song_metadata['album']
            current_track = a + 1
            total_tracks = album.nb_tracks
            percentage = (current_track / total_tracks) * 100
            percentage_rounded = round(percentage, 2)

            # Print JSON progress
            print(json.dumps({
                "status": "progress",
                "type": "album",
                "current_track": current_track,
                "total_tracks": total_tracks,
                "percentage": percentage_rounded,
                "album": album_name,
                "song": song_name,
                "artist": artist_name
            }))  

            song = f"{song_name} - {artist_name}"
            c_preferences = deepcopy(self.__preferences)
            c_preferences.song_metadata = c_song_metadata.copy()
            c_preferences.ids = c_song_metadata['ids']
            c_preferences.link = f"https://open.spotify.com/track/{c_preferences.ids}"
    
            try:
                track = EASY_DW(c_preferences).download_try()
            except TrackNotFound:
                track = Track(
                    c_song_metadata,
                    None, None,
                    None, None, None,
                )

                track.success = False
                print(f"Track not found: {song} :(")

            tracks.append(track)

        if self.__make_zip:
            song_quality = tracks[0].quality

            zip_name = create_zip(
                tracks,
                output_dir = self.__output_dir,
                song_metadata = self.__song_metadata,
                song_quality = song_quality,
                method_save = self.__method_save
            )

            album.zip_path = zip_name

        # Print done status
        print(json.dumps({
            "status": "done",
            "type": "album",
            "album": self.__song_metadata['album'],
            "artist": self.__song_metadata['artist']
        }))

        return album

class DW_PLAYLIST:
    def __init__(
        self,
        preferences: Preferences
    ) -> None:

        self.__preferences = preferences
        self.__ids = self.__preferences.ids
        self.__json_data = preferences.json_data
        self.__make_zip = self.__preferences.make_zip
        self.__output_dir = self.__preferences.output_dir
        self.__song_metadata = self.__preferences.song_metadata

    def dw(self) -> Playlist:
        # Initializing message
        playlist_name = self.__json_data.get('name', 'unknown')
        owner = self.__json_data.get('owner', {}).get('display_name', 'unknown')
        total_tracks = self.__json_data.get('tracks', {}).get('total', 'unknown')
        print(json.dumps({
            "status": "initializing",
            "type": "playlist",
            "name": playlist_name,
            "owner": owner,
            "total_tracks": total_tracks
        }))

        playlist = Playlist()
        tracks = playlist.tracks

        for c_song_metadata in self.__song_metadata:
            if type(c_song_metadata) is str:
                print(f"Track not found {c_song_metadata} :(")
                continue

            c_preferences = deepcopy(self.__preferences)
            c_preferences.ids = c_song_metadata['ids']
            c_preferences.song_metadata = c_song_metadata

            track = EASY_DW(c_preferences).easy_dw()

            if not track.success:
                song = f"{c_song_metadata['music']} - {c_song_metadata['artist']}"
                print(f"Cannot download {song}")

            tracks.append(track)

        if self.__make_zip:
            playlist_title = self.__json_data['name']
            zip_name = f"{self.__output_dir}/{playlist_title} [playlist {self.__ids}]"
            create_zip(tracks, zip_name = zip_name)
            playlist.zip_path = zip_name

        # Done message
        print(json.dumps({
            "status": "done",
            "type": "playlist",
            "name": playlist_name,
            "owner": owner,
            "total_tracks": total_tracks
        }))

        return playlist

    def dw2(self) -> Playlist:
        # Initializing message (if needed for dw2, else remove)
        playlist_name = self.__json_data.get('name', 'unknown')
        owner = self.__json_data.get('owner', {}).get('display_name', 'unknown')
        total_tracks = self.__json_data.get('tracks', {}).get('total', 'unknown')
        print(json.dumps({
            "status": "initializing",
            "type": "playlist",
            "name": playlist_name,
            "owner": owner,
            "total_tracks": total_tracks
        }))

        playlist = Playlist()
        tracks = playlist.tracks

        for c_song_metadata in self.__song_metadata:
            if type(c_song_metadata) is str:
                print(f"Track not found {c_song_metadata} :(")
                continue

            c_preferences = deepcopy(self.__preferences)
            c_preferences.ids = c_song_metadata['ids']
            c_preferences.song_metadata = c_song_metadata

            track = EASY_DW(c_preferences).get_no_dw_track()

            if not track.success:
                song = f"{c_song_metadata['music']} - {c_song_metadata['artist']}"
                print(f"Cannot download {song}")

            tracks.append(track)

        download_cli(self.__preferences)

        if self.__make_zip:
            playlist_title = self.__json_data['name']
            zip_name = f"{self.__output_dir}/{playlist_title} [playlist {self.__ids}]"
            create_zip(tracks, zip_name = zip_name)
            playlist.zip_path = zip_name

        # Done message
        print(json.dumps({
            "status": "done",
            "type": "playlist",
            "name": playlist_name,
            "owner": owner,
            "total_tracks": total_tracks
        }))

        return playlist

class DW_EPISODE:
    def __init__(
        self,
        preferences: Preferences
    ) -> None:

        self.__preferences = preferences

    def dw(self) -> Episode:
        episode = EASY_DW(self.__preferences).download_eps()

        return episode

    def dw2(self) -> Episode:
        episode = EASY_DW(self.__preferences).get_no_dw_track()
        download_cli(self.__preferences)

        return episode