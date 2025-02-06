from deezspot.deezloader.dee_api import API
from copy import deepcopy
from os.path import isfile
import re
from pathlib import Path
import requests
import os
from deezspot.deezloader.deegw_api import API_GW
from deezspot.deezloader.deezer_settings import qualities
from deezspot.libutils.others_settings import answers
from deezspot.__taggers__ import write_tags, check_track
from deezspot.deezloader.__download_utils__ import decryptfile, gen_song_hash
from deezspot.exceptions import (
    TrackNotFound,
    NoRightOnMedia,
    QualityNotFound,
)
from deezspot.models import (
    Track,
    Album,
    Playlist,
    Preferences,
    Episode,
)
from deezspot.deezloader.__utils__ import (
    check_track_ids,
    check_track_md5,
    check_track_token,
)
from deezspot.libutils.utils import (
    set_path,
    trasform_sync_lyric,
    create_zip,
)
import json
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen import File

class Download_JOB:

    @classmethod
    def __get_url(
        cls,
        c_track: Track,  
        quality_download: str
    ) -> dict:
        if c_track.get('__TYPE__') == 'episode':
            return {
                "media": [{
                    "sources": [{
                        "url": c_track.get('EPISODE_DIRECT_STREAM_URL')
                    }]
                }]
            }
        else:
            c_md5, c_media_version = check_track_md5(c_track)
            track_id_key = check_track_ids(c_track)
            c_ids = c_track.get(track_id_key, "")
            n_quality = qualities[quality_download]['n_quality']

            if not c_md5:
                raise ValueError("MD5_ORIGIN is missing")
            if not c_media_version:
                raise ValueError("MEDIA_VERSION is missing")
            if not c_ids:
                raise ValueError(f"{track_id_key} is missing")

            c_song_hash = gen_song_hash(
                c_md5, n_quality,
                c_ids, c_media_version
            )

            c_media_url = API_GW.get_song_url(c_md5[0], c_song_hash)

            return {
                "media": [
                    {
                        "sources": [
                            {
                                "url": c_media_url
                            }
                        ]
                    }
                ]
            }
        
    @classmethod
    def check_sources(
        cls,
        infos_dw: list,
        quality_download: str  
    ) -> list:
        # Preprocess episodes separately
        medias = []
        for track in infos_dw:
            if track.get('__TYPE__') == 'episode':
                media_json = cls.__get_url(track, quality_download)
                medias.append(media_json)

        # For non-episodes, gather tokens
        non_episode_tracks = [c_track for c_track in infos_dw if c_track.get('__TYPE__') != 'episode']
        tokens = [check_track_token(c_track) for c_track in non_episode_tracks]

        def chunk_list(lst, chunk_size):
            """Yield successive chunk_size chunks from lst."""
            for i in range(0, len(lst), chunk_size):
                yield lst[i:i + chunk_size]

        # Prepare list for media results for non-episodes
        non_episode_medias = []

        # Split tokens into chunks of 25
        for tokens_chunk in chunk_list(tokens, 25):
            try:
                chunk_medias = API_GW.get_medias_url(tokens_chunk, quality_download)
                # Post-process each returned media in the chunk
                for idx in range(len(chunk_medias)):
                    if "errors" in chunk_medias[idx]:
                        c_media_json = cls.__get_url(non_episode_tracks[len(non_episode_medias) + idx], quality_download)
                        chunk_medias[idx] = c_media_json
                    else:
                        if not chunk_medias[idx]['media']:
                            c_media_json = cls.__get_url(non_episode_tracks[len(non_episode_medias) + idx], quality_download)
                            chunk_medias[idx] = c_media_json
                        elif len(chunk_medias[idx]['media'][0]['sources']) == 1:
                            c_media_json = cls.__get_url(non_episode_tracks[len(non_episode_medias) + idx], quality_download)
                            chunk_medias[idx] = c_media_json
                non_episode_medias.extend(chunk_medias)
            except NoRightOnMedia:
                for c_track in tokens_chunk:
                    # Find the corresponding full track info from non_episode_tracks
                    track_index = len(non_episode_medias)
                    c_media_json = cls.__get_url(non_episode_tracks[track_index], quality_download)
                    non_episode_medias.append(c_media_json)

        # Now, merge the medias. We need to preserve the original order.
        # We'll create a final list that contains media for each track in infos_dw.
        final_medias = []
        episode_idx = 0
        non_episode_idx = 0
        for track in infos_dw:
            if track.get('__TYPE__') == 'episode':
                final_medias.append(medias[episode_idx])
                episode_idx += 1
            else:
                final_medias.append(non_episode_medias[non_episode_idx])
                non_episode_idx += 1

        return final_medias

class EASY_DW:
    def __init__(
        self,
        infos_dw: dict,
        preferences: Preferences
    ) -> None:
        
        self.__preferences = preferences

        self.__infos_dw = infos_dw
        self.__ids = preferences.ids
        self.__link = preferences.link
        self.__output_dir = preferences.output_dir
        self.__method_save = preferences.method_save
        self.__not_interface = preferences.not_interface
        self.__quality_download = preferences.quality_download
        self.__recursive_quality = preferences.recursive_quality
        self.__recursive_download = preferences.recursive_download


        if self.__infos_dw.get('__TYPE__') == 'episode':
            self.__song_metadata = {
                'music': self.__infos_dw.get('EPISODE_TITLE', ''),
                'artist': self.__infos_dw.get('SHOW_NAME', ''),
                'album': self.__infos_dw.get('SHOW_NAME', ''),
                'date': self.__infos_dw.get('EPISODE_PUBLISHED_TIMESTAMP', '').split()[0],
                'genre': 'Podcast',
                'explicit': self.__infos_dw.get('SHOW_IS_EXPLICIT', '2'),
                'disc': 1,
                'track': 1,
                'duration': int(self.__infos_dw.get('DURATION', 0)),
                'isrc': None
            }
            self.__download_type = "episode"
        else:
            self.__song_metadata = preferences.song_metadata
            self.__download_type = "track"

        self.__c_quality = qualities[self.__quality_download]
        self.__fallback_ids = self.__ids

        self.__set_quality()
        self.__write_track()

    def __track_already_exists(self, title, album):
        for root, _, files in os.walk(self.__output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                lower_file = file.lower()
                try:
                    existing_title = None
                    existing_album = None
                    if lower_file.endswith('.flac'):
                        audio = FLAC(file_path)
                        existing_title = audio.get('title', [None])[0]
                        existing_album = audio.get('album', [None])[0]
                    elif lower_file.endswith('.mp3'):
                        audio = MP3(file_path, ID3=ID3)
                        existing_title = audio.get('TIT2', [None])[0]
                        existing_album = audio.get('TALB', [None])[0]
                    elif lower_file.endswith('.m4a'):
                        audio = MP4(file_path)
                        existing_title = audio.get('\xa9nam', [None])[0]
                        existing_album = audio.get('\xa9alb', [None])[0]
                    elif lower_file.endswith(('.ogg', '.wav')):
                        audio = File(file_path)
                        existing_title = audio.get('title', [None])[0]
                        existing_album = audio.get('album', [None])[0]
                    if existing_title == title and existing_album == album:
                        return True
                except:
                    continue
        return False

    def __set_quality(self) -> None:
        self.__file_format = self.__c_quality['f_format']
        self.__song_quality = self.__c_quality['s_quality']

    def __set_song_path(self) -> None:
        # If the Preferences object has custom formatting strings, pass them on.
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

    def easy_dw(self) -> Track:
        if self.__infos_dw.get('__TYPE__') == 'episode':
            pic = self.__infos_dw.get('EPISODE_IMAGE_MD5', '')
        else:
            pic = self.__infos_dw['ALB_PICTURE']
        image = API.choose_img(pic)
        self.__song_metadata['image'] = image
        song = f"{self.__song_metadata['music']} - {self.__song_metadata['artist']}"

        # Check if track already exists based on metadata
        current_title = self.__song_metadata['music']
        current_album = self.__song_metadata['album']
        if self.__track_already_exists(current_title, current_album):
            print(json.dumps({
                "status": "skipped",
                "type": self.__download_type,
                "album": current_album,
                "song": current_title,
                "artist": self.__song_metadata['artist'],
                "reason": "Track already exists"
            }))
            skipped_track = Track(
                self.__song_metadata,
                None, None, None,
                self.__link, self.__ids
            )
            skipped_track.success = False
            return skipped_track

        # Initial download start status
        print(json.dumps({
            "status": "downloading",
            "type": self.__download_type,
            "album": self.__song_metadata['album'],
            "song": self.__song_metadata['music'],
            "artist": self.__song_metadata['artist']
        }))

        try:
            if self.__infos_dw.get('__TYPE__') == 'episode':
                try:
                    return self.download_episode_try()
                except Exception as e:
                    self.__c_track.success = False
                    raise e
            else:
                self.download_try()
                print(json.dumps({
                    "status": "done",
                    "type": "track",
                    "album": self.__song_metadata['album'],
                    "song": self.__song_metadata['music'],
                    "artist": self.__song_metadata['artist']
                }))
        except TrackNotFound:
            try:
                self.__fallback_ids = API.not_found(song, self.__song_metadata['music'])
                self.__infos_dw = API_GW.get_song_data(self.__fallback_ids)

                media = Download_JOB.check_sources(
                    [self.__infos_dw], self.__quality_download
                )

                self.__infos_dw['media_url'] = media[0]
                self.download_try()
            except TrackNotFound:
                self.__c_track = Track(
                    self.__song_metadata,
                    None, None,
                    None, None, None,
                )

                self.__c_track.success = False

        self.__c_track.md5_image = pic

        return self.__c_track

    def download_try(self) -> Track:
        if isfile(self.__song_path) and check_track(self.__c_track):
            if self.__recursive_download:
                return self.__c_track

            ans = input(
                f"Track \"{self.__song_path}\" already exists, do you want to redownload it?(y or n):"
            )

            if not ans in answers:
                return self.__c_track

        try:
            media_list = self.__infos_dw['media_url']['media']
            song_link = media_list[0]['sources'][0]['url']
            
            try:
                crypted_audio = API_GW.song_exist(song_link)
            except TrackNotFound:
                song = self.__song_metadata['music']
                artist = self.__song_metadata['artist']
                
                if self.__file_format == '.flac':
                    print(f"\n⚠ {song} - {artist} is not available in FLAC format. Trying MP3...")
                    self.__quality_download = 'MP3_320'
                    self.__file_format = '.mp3'
                    self.__song_path = self.__song_path.rsplit('.', 1)[0] + '.mp3'
                    
                    media = Download_JOB.check_sources(
                        [self.__infos_dw], 'MP3_320'
                    )
                    
                    if media:
                        self.__infos_dw['media_url'] = media[0]
                        song_link = media[0]['media'][0]['sources'][0]['url']
                        crypted_audio = API_GW.song_exist(song_link)
                    else:
                        raise TrackNotFound(f"Track {song} - {artist} not available")
                
                else:
                    msg = f"\n⚠ The {song} - {artist} can't be downloaded in {self.__quality_download} quality :( ⚠\n"
                    
                    if not self.__recursive_quality:
                        raise QualityNotFound(msg=msg)
                    
                    print(msg)
                    
                    for c_quality in qualities:
                        if self.__quality_download == c_quality:
                            continue
                            
                        print(f"🛈 Trying to download {song} - {artist} in {c_quality}")
                        
                        media = Download_JOB.check_sources(
                            [self.__infos_dw], c_quality
                        )
                        
                        if media:
                            self.__infos_dw['media_url'] = media[0]
                            song_link = media[0]['media'][0]['sources'][0]['url']
                            try:
                                crypted_audio = API_GW.song_exist(song_link)
                                self.__c_quality = qualities[c_quality]
                                self.__set_quality()
                                break
                            except TrackNotFound:
                                if c_quality == "MP3_128":
                                    raise TrackNotFound(f"Error with {song} - {artist}", self.__link)
                                continue
            
            c_crypted_audio = crypted_audio.iter_content(2048)
            self.__fallback_ids = check_track_ids(self.__infos_dw)
            
            try:
                self.__write_track()
                decryptfile(
                    c_crypted_audio, self.__fallback_ids, self.__song_path
                )
                self.__add_more_tags()
                write_tags(self.__c_track)
            
            except Exception as e:
                if isfile(self.__song_path):
                    os.remove(self.__song_path)
                raise TrackNotFound(f"Failed to process {self.__song_path}: {str(e)}")
                
            return self.__c_track
            
        except Exception as e:
            raise TrackNotFound(self.__link) from e

    def download_episode_try(self) -> Episode:
        try:
            direct_url = self.__infos_dw.get('EPISODE_DIRECT_STREAM_URL')
            if not direct_url:
                raise TrackNotFound("No direct stream URL found")

            os.makedirs(os.path.dirname(self.__song_path), exist_ok=True)

            response = requests.get(direct_url, stream=True)
            response.raise_for_status()

            content_length = response.headers.get('content-length')
            total_size = int(content_length) if content_length else None

            downloaded = 0
            with open(self.__song_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        size = f.write(chunk)
                        downloaded += size
                        # Removed episode progress updates

            self.__c_track.success = True
            self.__write_episode()
            write_tags(self.__c_track)
        
            return self.__c_track

        except Exception as e:
            if isfile(self.__song_path):
                os.remove(self.__song_path)
            self.__c_track.success = False
            raise TrackNotFound(f"Episode download failed: {str(e)}")

    def __add_more_tags(self) -> None:
        contributors = self.__infos_dw.get('SNG_CONTRIBUTORS', {})

        if "author" in contributors:
            self.__song_metadata['author'] = " & ".join(
                contributors['author']
            )
        else:
            self.__song_metadata['author'] = ""

        if "composer" in contributors:
            self.__song_metadata['composer'] = " & ".join(
                contributors['composer']
            )
        else:
            self.__song_metadata['composer'] = ""

        if "lyricist" in contributors:
            self.__song_metadata['lyricist'] = " & ".join(
                contributors['lyricist']
            )
        else:
            self.__song_metadata['lyricist'] = ""

        if "composerlyricist" in contributors:
            self.__song_metadata['composer'] = " & ".join(
                contributors['composerlyricist']
            )
        else:
            self.__song_metadata['composerlyricist'] = ""

        if "version" in self.__infos_dw:
            self.__song_metadata['version'] = self.__infos_dw['VERSION']
        else:
            self.__song_metadata['version'] = ""

        self.__song_metadata['lyric'] = ""
        self.__song_metadata['copyright'] = ""
        self.__song_metadata['lyricist'] = ""
        self.__song_metadata['lyric_sync'] = []

        if self.__infos_dw.get('LYRICS_ID', 0) != 0:
            need = API_GW.get_lyric(self.__ids)

            if "LYRICS_SYNC_JSON" in need:
                self.__song_metadata['lyric_sync'] = trasform_sync_lyric(
                    need['LYRICS_SYNC_JSON']
                )

            self.__song_metadata['lyric'] = need['LYRICS_TEXT']
            self.__song_metadata['copyright'] = need['LYRICS_COPYRIGHTS']
            self.__song_metadata['lyricist'] = need['LYRICS_WRITERS']
            
class DW_TRACK:
    def __init__(
        self,
        preferences: Preferences
    ) -> None:

        self.__preferences = preferences
        self.__ids = self.__preferences.ids
        self.__song_metadata = self.__preferences.song_metadata
        self.__quality_download = self.__preferences.quality_download

    def dw(self) -> Track:
        infos_dw = API_GW.get_song_data(self.__ids)

        media = Download_JOB.check_sources(
            [infos_dw], self.__quality_download
        )

        infos_dw['media_url'] = media[0]

        track = EASY_DW(infos_dw, self.__preferences).easy_dw()

        if not track.success:
            song = f"{self.__song_metadata['music']} - {self.__song_metadata['artist']}"
            error_msg = f"Cannot download {song}, maybe it's not available in this format?"

            raise TrackNotFound(message = error_msg)

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
        self.__quality_download = self.__preferences.quality_download

        self.__song_metadata_items = self.__song_metadata.items()

    def dw(self) -> Album:
        infos_dw = API_GW.get_album_data(self.__ids)['data']

        md5_image = infos_dw[0]['ALB_PICTURE']
        image = API.choose_img(md5_image)
        self.__song_metadata['image'] = image

        album = Album(self.__ids)
        album.image = image
        album.md5_image = md5_image
        album.nb_tracks = self.__song_metadata['nb_tracks']
        album.album_name = self.__song_metadata['album']
        album.upc = self.__song_metadata['upc']
        tracks = album.tracks
        album.tags = self.__song_metadata

        # Get media URLs using the splitting approach
        medias = Download_JOB.check_sources(
            infos_dw, self.__quality_download
        )
        print(json.dumps({
            "status": "initializing",
            "type": "album",
            "album": self.__song_metadata['album'],
            "artist": self.__song_metadata['artist']
        }))

        total_tracks = len(infos_dw)
        for a in range(total_tracks):
            track_number = a + 1
            c_infos_dw = infos_dw[a]
            
            # Build the core track metadata from API response
            contributors = c_infos_dw.get('SNG_CONTRIBUTORS', {})
            
            # Handle artists with featuring
            main_artist = " & ".join(contributors.get('main_artist', []))
            featuring = " & ".join(contributors.get('featuring', []))
            artist_parts = [main_artist]
            if featuring:
                artist_parts.append(f"(feat. {featuring})")
                
            c_song_metadata = {
                'music': c_infos_dw.get('SNG_TITLE', 'Unknown'),
                'artist': " ".join(artist_parts),
                'album': self.__song_metadata['album'],
                'date': c_infos_dw.get('DIGITAL_RELEASE_DATE', ''),
                'genre': self.__song_metadata.get('genre', 'Latin Music'),
                'tracknum': f"{track_number}",
                'discnum': f"{c_infos_dw.get('DISK_NUMBER', 1)}",
                'isrc': c_infos_dw.get('ISRC', ''),
                'composer': " & ".join(contributors.get('composer', [])),
                'album_artist': self.__song_metadata['artist'],
                'publisher': 'CanZion R',
                'duration': int(c_infos_dw.get('DURATION', 0)),
                'explicit': c_infos_dw.get('EXPLICIT_LYRICS', '0') == '1' and '1' or '0'
            }
            # Print progress status for each track
            current_track_str = f"{track_number}/{total_tracks}"
            print(json.dumps({
                "status": "progress",
                "type": "album",
                "track": c_song_metadata['music'],
                "current_track": current_track_str,
                "album": c_song_metadata['album']
            }))

            # Merge with album-level metadata (without overriding track-specific data)
            for key, item in self.__song_metadata_items:
                if key not in c_song_metadata:  # Don't override already set fields
                    if isinstance(item, list):
                        c_song_metadata[key] = self.__song_metadata[key][a] if len(self.__song_metadata[key]) > a else 'Unknown'
                    else:
                        c_song_metadata[key] = self.__song_metadata[key]

            c_infos_dw['media_url'] = medias[a]
            c_preferences = deepcopy(self.__preferences)
            c_preferences.song_metadata = c_song_metadata.copy()
            c_preferences.ids = c_infos_dw['SNG_ID']
            c_preferences.link = f"https://deezer.com/track/{c_preferences.ids}"

            try:
                track = EASY_DW(c_infos_dw, c_preferences).download_try()
            except TrackNotFound:
                try:
                    song = f"{c_song_metadata['music']} - {c_song_metadata['artist']}"
                    ids = API.not_found(song, c_song_metadata['music'])
                    c_infos_dw = API_GW.get_song_data(ids)
                    c_media = Download_JOB.check_sources([c_infos_dw], self.__quality_download)
                    c_infos_dw['media_url'] = c_media[0]
                    track = EASY_DW(c_infos_dw, c_preferences).download_try()
                except TrackNotFound:
                    track = Track(c_song_metadata, None, None, None, None, None)
                    track.success = False
                    print(f"Track not found: {song} :(")
            tracks.append(track)

        if self.__make_zip:
            song_quality = tracks[0].quality if tracks else 'Unknown'
            # Pass along custom directory format if set
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
        self.__quality_download = self.__preferences.quality_download

    def dw(self) -> Playlist:
        infos_dw = API_GW.get_playlist_data(self.__ids)['data']
        
        # Extract playlist metadata
        playlist_name = self.__json_data['title']
        total_tracks = len(infos_dw)

        print(json.dumps({
            "status": "initializing",
            "type": "playlist",
            "name": playlist_name,
            "total_tracks": total_tracks
        }))

        playlist = Playlist()
        tracks = playlist.tracks

        medias = Download_JOB.check_sources(
            infos_dw, self.__quality_download
        )

        for idx, (c_infos_dw, c_media, c_song_metadata) in enumerate(zip(infos_dw, medias, self.__song_metadata), 1):

            if type(c_song_metadata) is str:
                continue

            c_infos_dw['media_url'] = c_media
            c_preferences = deepcopy(self.__preferences)
            c_preferences.ids = c_infos_dw['SNG_ID']
            c_preferences.song_metadata = c_song_metadata

            track = EASY_DW(c_infos_dw, c_preferences).easy_dw()

            current_track_str = f"{idx}/{total_tracks}"
            print(json.dumps({
                "status": "progress",
                "type": "playlist",
                "track": c_song_metadata['music'],
                "current_track": current_track_str
            }))

            if not track.success:
                song = f"{c_song_metadata['music']} - {c_song_metadata['artist']}"
                print(f"Cannot download {song}")

            tracks.append(track)

        if self.__make_zip:
            playlist_title = self.__json_data['title']
            zip_name = f"{self.__output_dir}/{playlist_title} [playlist {self.__ids}]"
            create_zip(tracks, zip_name = zip_name)
            playlist.zip_path = zip_name

        print(json.dumps({
            "status": "done",
            "type": "playlist",
            "name": playlist_name,
            "total_tracks": total_tracks
        }))
        
        return playlist

class DW_EPISODE:
    def __init__(
        self,
        preferences: Preferences
    ) -> None:
        self.__preferences = preferences
        self.__ids = preferences.ids
        self.__output_dir = preferences.output_dir
        self.__method_save = preferences.method_save
        self.__not_interface = preferences.not_interface
        self.__quality_download = preferences.quality_download
        
    def __sanitize_filename(self, filename: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '', filename)[:200]

    def dw(self) -> Track:
        infos_dw = API_GW.get_episode_data(self.__ids)
        infos_dw['__TYPE__'] = 'episode'
        
        self.__preferences.song_metadata = {
            'music': infos_dw.get('EPISODE_TITLE', ''),
            'artist': infos_dw.get('SHOW_NAME', ''),
            'album': infos_dw.get('SHOW_NAME', ''),
            'date': infos_dw.get('EPISODE_PUBLISHED_TIMESTAMP', '').split()[0],
            'genre': 'Podcast',
            'explicit': infos_dw.get('SHOW_IS_EXPLICIT', '2'),
            'duration': int(infos_dw.get('DURATION', 0)),
        }
        
        try:
            direct_url = infos_dw.get('EPISODE_DIRECT_STREAM_URL')
            if not direct_url:
                raise TrackNotFound("No direct URL found")
            
            safe_filename = self.__sanitize_filename(self.__preferences.song_metadata['music'])
            Path(self.__output_dir).mkdir(parents=True, exist_ok=True)
            output_path = os.path.join(self.__output_dir, f"{safe_filename}.mp3")
            
            response = requests.get(direct_url, stream=True)
            response.raise_for_status()

            content_length = response.headers.get('content-length')
            total_size = int(content_length) if content_length else None

            downloaded = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        size = f.write(chunk)
                        downloaded += size
                        # Removed progress reporting here
            
            episode = Track(
                self.__preferences.song_metadata,
                output_path,
                '.mp3',
                self.__quality_download, 
                f"https://www.deezer.com/episode/{self.__ids}",
                self.__ids
            )
            episode.success = True
            return episode
            
        except Exception as e:
            if 'output_path' in locals() and os.path.exists(output_path):
                os.remove(output_path)
            raise TrackNotFound(f"Episode download failed: {str(e)}")
