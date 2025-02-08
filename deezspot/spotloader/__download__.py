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
from mutagen import File
from mutagen.easyid3 import EasyID3
from mutagen.oggvorbis import OggVorbis
from mutagen.flac import FLAC
from mutagen.mp4 import MP4

# --- Global retry counter variables ---
GLOBAL_RETRY_COUNT = 0
GLOBAL_MAX_RETRIES = 100  # Adjust this value as needed

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
        
        self.__preferences = preferences

        self.__ids = preferences.ids
        self.__link = preferences.link
        self.__output_dir = preferences.output_dir
        self.__method_save = preferences.method_save
        self.__song_metadata = preferences.song_metadata
        self.__not_interface = preferences.not_interface
        self.__quality_download = preferences.quality_download or "NORMAL"
        self.__recursive_download = preferences.recursive_download
        self.__type = "episode" if preferences.is_episode else "track"  # New type parameter
        self.__real_time_dl = preferences.real_time_dl

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
        # Retrieve custom formatting strings from preferences, if any.
        custom_dir_format = getattr(self.__preferences, 'custom_dir_format', None)
        custom_track_format = getattr(self.__preferences, 'custom_track_format', None)
        self.__song_path = set_path(
            self.__song_metadata,
            self.__output_dir,
            self.__song_quality,
            self.__file_format,
            self.__method_save,
            custom_dir_format=custom_dir_format,
            custom_track_format=custom_track_format
        )

    def __set_episode_path(self) -> None:
        custom_dir_format = getattr(self.__preferences, 'custom_dir_format', None)
        custom_track_format = getattr(self.__preferences, 'custom_track_format', None)
        self.__song_path = set_path(
            self.__song_metadata,
            self.__output_dir,
            self.__song_quality,
            self.__file_format,
            self.__method_save,
            is_episode=True,
            custom_dir_format=custom_dir_format,
            custom_track_format=custom_track_format
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

    def get_no_dw_track(self) -> Track:
        return self.__c_track

    def easy_dw(self) -> Track:
        # Request the image data
        pic = self.__song_metadata['image']
        image = request(pic).content
        self.__song_metadata['image'] = image

        # Print initial "downloading" status for track
        print(json.dumps({
            "status": "downloading",
            "type": "track",
            "album": self.__song_metadata.get("album", ""),
            "song": self.__song_metadata.get("music", ""),
            "artist": self.__song_metadata.get("artist", "")
        }))

        try:
            self.download_try()
        except Exception as e:
            traceback.print_exc()
            raise e

        return self.__c_track

    def track_exists(self, title, album):
        # Ensure the final song path is set
        if not hasattr(self, '_EASY_DW__song_path') or not self.__song_path:
            self.__set_song_path()

        # Use only the final directory for scanning
        final_dir = os.path.dirname(self.__song_path)
        
        # If the final directory doesn't exist, there are no files to check
        if not os.path.exists(final_dir):
            return False

        # Iterate over files only in the final directory
        for file in os.listdir(final_dir):
            if file.lower().endswith(('.mp3', '.ogg', '.flac', '.wav', '.m4a', '.opus')):
                file_path = os.path.join(final_dir, file)
                existing_title, existing_album = self.read_metadata(file_path)
                if existing_title == title and existing_album == album:
                    return True
        return False


    def read_metadata(self, file_path):
        try:
            if not os.path.isfile(file_path):
                return None, None
            audio = File(file_path)
            if audio is None:
                return None, None
            title = None
            album = None
            if file_path.endswith('.mp3'):
                try:
                    audio = EasyID3(file_path)
                    title = audio.get('title', [None])[0]
                    album = audio.get('album', [None])[0]
                except Exception:
                    pass
            elif file_path.endswith('.ogg'):
                audio = OggVorbis(file_path)
                title = audio.get('title', [None])[0]
                album = audio.get('album', [None])[0]
            elif file_path.endswith('.flac'):
                audio = FLAC(file_path)
                title = audio.get('title', [None])[0]
                album = audio.get('album', [None])[0]
            elif file_path.endswith('.m4a'):
                audio = MP4(file_path)
                title = audio.get('\xa9nam', [None])[0]
                album = audio.get('\xa9alb', [None])[0]
            else:
                return None, None
            return title, album
        except Exception as e:
            print(f"Error reading metadata from {file_path}: {e}")
            return None, None

    def download_try(self) -> Track:
        current_title = self.__song_metadata.get('music')
        current_album = self.__song_metadata.get('album')
        current_artist = self.__song_metadata.get('artist')

        if self.track_exists(current_title, current_album):
            print(json.dumps({
                "status": "done",
                "type": "track",
                "album": current_album,
                "song": current_title,
                "artist": current_artist
            }))
            return self.__c_track

        retries = 0
        retry_delay = 30  # start with 30 seconds delay
        max_retries = 5

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
                    if self.__real_time_dl and self.__song_metadata.get("duration"):
                        duration = self.__song_metadata["duration"]
                        if duration > 0:
                            rate_limit = total_size / duration
                            chunk_size = 4096
                            bytes_written = 0
                            start_time = time.time()
                            while True:
                                chunk = c_stream.read(chunk_size)
                                if not chunk:
                                    break
                                f.write(chunk)
                                bytes_written += len(chunk)
                                print(json.dumps({
                                    "status": "real_time",
                                    "song": self.__song_metadata.get("music", ""),
                                    "artist": self.__song_metadata.get("artist", ""),
                                    "time_elapsed": int((time.time() - start_time)*1000),
                                    "percentage": bytes_written / total_size
                                }))
                                expected_time = bytes_written / rate_limit
                                if expected_time > (time.time() - start_time):
                                    time.sleep(expected_time - (time.time() - start_time))
                        else:
                            data = c_stream.read(total_size)
                            f.write(data)
                    else:
                        data = c_stream.read(total_size)
                        f.write(data)
                    c_stream.close()
                break
            except Exception as e:
                global GLOBAL_RETRY_COUNT
                GLOBAL_RETRY_COUNT += 1
                retries += 1
                print(json.dumps({
                    "status": "retrying",
                    "retry_count": retries,
                    "seconds_left": retry_delay,
                    "song": self.__song_metadata['music'],
                    "artist": self.__song_metadata['artist'],
                    "album": self.__song_metadata['album'],
                    "error": str(e)
                }))
                if retries >= max_retries or GLOBAL_RETRY_COUNT >= GLOBAL_MAX_RETRIES:
                    raise Exception(f"Maximum retry limit reached (local: {max_retries}, global: {GLOBAL_MAX_RETRIES}).")
                time.sleep(retry_delay)
                retry_delay += 30
        try:
            self.__convert_audio()
        except Exception as e:
            print(json.dumps({
                "status": "retrying",
                "retry_count": retries,
                "action": "convert_audio",
                "song": self.__song_metadata['music'],
                "artist": self.__song_metadata['artist'],
                "album": self.__song_metadata['album'],
                "error": str(e)
            }))
            time.sleep(retry_delay)
            retry_delay += 30
            self.__convert_audio()

        self.__write_track()
        write_tags(self.__c_track)
        print(json.dumps({
            "status": "done",
            "type": "track",
            "album": self.__song_metadata.get("album", ""),
            "song": self.__song_metadata.get("music", ""),
            "artist": self.__song_metadata.get("artist", "")
        }))
        return self.__c_track

    def download_eps(self) -> Episode:
        retry_delay = 30
        retries = 0
        max_retries = 5
        if isfile(self.__song_path) and check_track(self.__c_episode):
            ans = input(
                f"Episode \"{self.__song_path}\" already exists, do you want to redownload it?(y or n):"
            )
            if not ans in answers:
                return self.__c_episode
        episode_id = EpisodeId.from_base62(self.__ids)
        while True:
            try:
                stream = Download_JOB.session.content_feeder().load_episode(
                    episode_id,
                    AudioQuality(self.__dw_quality),
                    False,
                    None
                )
                break
            except Exception as e:
                global GLOBAL_RETRY_COUNT
                GLOBAL_RETRY_COUNT += 1
                retries += 1
                print(json.dumps({
                    "status": "retrying",
                    "retry_count": retries,
                    "seconds_left": retry_delay,
                    "song": self.__song_metadata['music'],
                    "artist": self.__song_metadata['artist'],
                    "album": self.__song_metadata['album'],
                    "error": str(e)
                }))
                if retries >= max_retries or GLOBAL_RETRY_COUNT >= GLOBAL_MAX_RETRIES:
                    raise Exception(f"Maximum retry limit reached (local: {max_retries}, global: {GLOBAL_MAX_RETRIES}).")
                time.sleep(retry_delay)
                retry_delay += 30
        total_size = stream.input_stream.size
        os.makedirs(dirname(self.__song_path), exist_ok=True)
        with open(self.__song_path, "wb") as f:
            c_stream = stream.input_stream.stream()
            if self.__real_time_dl and self.__song_metadata.get("duration"):
                duration = self.__song_metadata["duration"]
                if duration > 0:
                    rate_limit = total_size / duration
                    chunk_size = 4096
                    bytes_written = 0
                    start_time = time.time()
                    while True:
                        chunk = c_stream.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_written += len(chunk)
                        expected_time = bytes_written / rate_limit
                        elapsed_time = time.time() - start_time
                        if expected_time > elapsed_time:
                            time.sleep(expected_time - elapsed_time)
                else:
                    data = c_stream.read(total_size)
                    f.write(data)
            else:
                data = c_stream.read(total_size)
                f.write(data)
            c_stream.close()
        try:
            self.__convert_audio()
        except Exception as e:
            print(json.dumps({
                "status": "retrying",
                "action": "convert_audio",
                "song": self.__song_metadata['music'],
                "artist": self.__song_metadata['artist'],
                "album": self.__song_metadata['album'],
                "error": str(e)
            }))
            time.sleep(retry_delay)
            retry_delay += 30
            self.__convert_audio()
        self.__write_episode()
        write_tags(self.__c_episode)
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
        print(json.dumps({
            "status": "initializing",
            "type": "album",
            "album": self.__song_metadata.get("album", ""),
            "artist": self.__song_metadata.get("artist", "")
        }))
        c_song_metadata = {}
        for key, item in self.__song_metadata_items:
            if type(item) is not list:
                c_song_metadata[key] = self.__song_metadata[key]
        total_tracks = album.nb_tracks
        for a in range(total_tracks):
            for key, item in self.__song_metadata_items:
                if type(item) is list:
                    c_song_metadata[key] = self.__song_metadata[key][a]
            song_name = c_song_metadata['music']
            artist_name = c_song_metadata['artist']
            album_name = c_song_metadata['album']
            current_track = a + 1
            print(json.dumps({
                "status": "progress",
                "type": "album",
                "track": song_name,
                "current_track": f"{current_track}/{total_tracks}",
                "album": c_song_metadata['album']
            }))
            c_preferences = deepcopy(self.__preferences)
            c_preferences.song_metadata = c_song_metadata.copy()
            c_preferences.ids = c_song_metadata['ids']
            c_preferences.link = f"https://open.spotify.com/track/{c_preferences.ids}"
            try:
                track = EASY_DW(c_preferences).download_try()
            except TrackNotFound:
                track = Track(c_song_metadata, None, None, None, None, None)
                track.success = False
                print(f"Track not found: {song_name} :(")
            tracks.append(track)
        if self.__make_zip:
            song_quality = tracks[0].quality
            custom_dir_format = getattr(self.__preferences, 'custom_dir_format', None)
            zip_name = create_zip(
                tracks,
                output_dir=self.__output_dir,
                song_metadata=self.__song_metadata,
                song_quality=song_quality,
                method_save=self.__method_save,
                custom_dir_format=custom_dir_format
            )
            album.zip_path = zip_name
        print(json.dumps({
            "status": "done",
            "type": "album",
            "album": album.album_name,
            "artist": self.__song_metadata.get("artist", "")
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
        playlist_name = self.__json_data.get('name', 'unknown')
        total_tracks = self.__json_data.get('tracks', {}).get('total', 'unknown')
        print(json.dumps({
            "status": "initializing",
            "type": "playlist",
            "name": playlist_name,
            "total_tracks": total_tracks
        }))

        # --- Prepare the m3u playlist file ---
        playlist_m3u_dir = os.path.join(self.__output_dir, "playlists")
        os.makedirs(playlist_m3u_dir, exist_ok=True)
        m3u_path = os.path.join(playlist_m3u_dir, f"{playlist_name}.m3u")
        if not os.path.exists(m3u_path):
            with open(m3u_path, "w", encoding="utf-8") as m3u_file:
                m3u_file.write("#EXTM3U\n")
        # -------------------------------------

        playlist = Playlist()
        tracks = playlist.tracks
        for i, c_song_metadata in enumerate(self.__song_metadata):
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
            # --- Append the final track path to the m3u file using a relative path ---
            if track.success and hasattr(track, 'song_path') and track.song_path:
                # Build the relative path from the playlists directory
                relative_path = os.path.relpath(
                    track.song_path,
                    start=os.path.join(self.__output_dir, "playlists")
                )
                with open(m3u_path, "a", encoding="utf-8") as m3u_file:
                    m3u_file.write(f"{relative_path}\n")
            # ---------------------------------------------------------------------
            print(json.dumps({
                "status": "progress",
                "type": "playlist",
                "track": c_song_metadata.get("music", ""),
                "current_track": f"{i+1}/{total_tracks}"
            }))
        print(json.dumps({
            "status": "done",
            "type": "playlist",
            "name": playlist_name,
            "total_tracks": total_tracks
        }))
        if self.__make_zip:
            playlist_title = self.__json_data['name']
            zip_name = f"{self.__output_dir}/{playlist_title} [playlist {self.__ids}]"
            create_zip(tracks, zip_name=zip_name)
            playlist.zip_path = zip_name
        return playlist

    def dw2(self) -> Playlist:
        playlist_name = self.__json_data.get('name', 'unknown')
        total_tracks = self.__json_data.get('tracks', {}).get('total', 'unknown')
        print(json.dumps({
            "status": "initializing",
            "type": "playlist",
            "name": playlist_name,
            "total_tracks": total_tracks
        }))
        playlist = Playlist()
        tracks = playlist.tracks
        for i, c_song_metadata in enumerate(self.__song_metadata):
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
            print(json.dumps({
                "status": "progress",
                "type": "playlist",
                "track": c_song_metadata.get("music", ""),
                "current_track": f"{i+1}/{total_tracks}"
            }))
        download_cli(self.__preferences)
        print(json.dumps({
            "status": "done",
            "type": "playlist",
            "name": playlist_name,
            "total_tracks": total_tracks
        }))
        if self.__make_zip:
            playlist_title = self.__json_data['name']
            zip_name = f"{self.__output_dir}/{playlist_title} [playlist {self.__ids}]"
            create_zip(tracks, zip_name=zip_name)
            playlist.zip_path = zip_name
        return playlist

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
