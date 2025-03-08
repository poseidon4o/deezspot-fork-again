# DeezSpot

DeezSpot is a Python library that enables downloading songs, albums, playlists, and podcasts from both Deezer and Spotify. This fork includes tweaks for use with the [spotizerr](https://github.com/Xoconoch/spotizerr) project.

## Features

- Download tracks, albums, playlists, and podcasts from both Deezer and Spotify
- Search for music by name or download directly using links
- Support for different audio quality options
- Download an artist's discography
- Smart link detection to identify and process different types of content
- Tag downloaded files with correct metadata
- Customizable file and directory naming formats

## Installation

### From PyPI (recommended)

```bash
pip install deezspot@https://github.com/Xoconoch/deezspot-fork-again.git
```

### From Source

```bash
git clone https://github.com/Xoconoch/deezspot-fork-again.git
cd deezspot-fork-again
pip install -e .
```

## Configuration

### Deezer Authentication

DeezSpot supports two methods of authentication for Deezer:

1. Using ARL token:
```python
from deezspot.deezloader import DeeLogin

# Authenticate with ARL
downloader = DeeLogin(arl="your_arl_token")
```

2. Using email and password:
```python
from deezspot.deezloader import DeeLogin

# Authenticate with email and password
downloader = DeeLogin(email="your_email", password="your_password")
```

### Spotify Authentication

For Spotify, you'll need a credentials file:

```python
from deezspot.spotloader import SpoLogin

# Authenticate with credentials file
downloader = SpoLogin(credentials_path="/path/to/credentials.json")
```

To create a credentials file, use a tool like [librespot-java](https://github.com/librespot-org/librespot-java) to generate it.

## Usage

### Downloading from Deezer

```python
from deezspot.deezloader import DeeLogin

# Initialize with your credentials
downloader = DeeLogin(arl="your_arl_token")

# Download a track
track = downloader.download_trackdee(
    "https://www.deezer.com/track/123456789",
    output_dir="./downloads",
    quality_download="FLAC"  # Options: MP3_320, FLAC, MP3_128
)

# Download an album
album = downloader.download_albumdee(
    "https://www.deezer.com/album/123456789",
    output_dir="./downloads",
    quality_download="MP3_320",
    make_zip=True  # Create a zip archive of the album
)

# Download a playlist
playlist = downloader.download_playlistdee(
    "https://www.deezer.com/playlist/123456789",
    output_dir="./downloads",
    quality_download="MP3_320"
)

# Download an artist's top tracks
tracks = downloader.download_artisttopdee(
    "https://www.deezer.com/artist/123456789",
    output_dir="./downloads"
)

# Search and download by name
track = downloader.download_name(
    artist="Artist Name",
    song="Song Title",
    output_dir="./downloads"
)
```

### Downloading from Spotify

```python
from deezspot.spotloader import SpoLogin

# Initialize with your credentials file
downloader = SpoLogin(credentials_path="/path/to/credentials.json")

# Download a track
track = downloader.download_track(
    "https://open.spotify.com/track/123456789",
    output_dir="./downloads",
    quality_download="VERY_HIGH"  # Options: VERY_HIGH, HIGH, NORMAL
)

# Download an album
album = downloader.download_album(
    "https://open.spotify.com/album/123456789",
    output_dir="./downloads",
    quality_download="HIGH",
    make_zip=True  # Create a zip archive of the album
)

# Download a playlist
playlist = downloader.download_playlist(
    "https://open.spotify.com/playlist/123456789",
    output_dir="./downloads"
)

# Download a podcast episode
episode = downloader.download_episode(
    "https://open.spotify.com/episode/123456789",
    output_dir="./downloads"
)

# Download an artist's discography
downloader.download_artist(
    "https://open.spotify.com/artist/123456789",
    album_type="album,single",  # Options: album, single, compilation, appears_on
    limit=50,  # Number of albums to retrieve
    output_dir="./downloads"
)
```

### Smart Download

Both the Deezer and Spotify interfaces provide a "smart" download function that automatically detects the type of content from the link:

```python
# For Deezer
result = downloader.download_smart("https://www.deezer.com/track/123456789")

# For Spotify
result = downloader.download_smart("https://open.spotify.com/album/123456789")
```

### Converting Spotify links to Deezer

DeezSpot can also convert Spotify links to Deezer for downloading with higher quality:

```python
# Convert and download a Spotify track using Deezer
track = downloader.download_trackspo("https://open.spotify.com/track/123456789")

# Convert and download a Spotify album using Deezer
album = downloader.download_albumspo("https://open.spotify.com/album/123456789")

# Convert and download a Spotify playlist using Deezer
playlist = downloader.download_playlistspo("https://open.spotify.com/playlist/123456789")
```

## Available Quality Options

### Deezer
- `MP3_320`: 320 kbps MP3
- `FLAC`: Lossless audio
- `MP3_128`: 128 kbps MP3

### Spotify
- `VERY_HIGH`: 320 kbps OGG
- `HIGH`: 160 kbps OGG
- `NORMAL`: 96 kbps OGG

## Common Parameters

Most download methods accept these common parameters:

- `output_dir`: Output directory for downloaded files (default: "Songs/")
- `quality_download`: Quality of audio files (see options above)
- `recursive_quality`: Try another quality if the selected one is not available (default: True)
- `recursive_download`: Try another API if the current one fails (default: True)
- `not_interface`: Hide download progress (default: False)
- `make_zip`: Create a zip archive for albums/playlists (default: False)
- `method_save`: How to save the downloads (default: varies by function)
- `custom_dir_format`: Custom directory naming format
- `custom_track_format`: Custom track naming format

## Custom Naming Formats

You can customize the output directory and file naming patterns:

```python
# Example of custom directory format
result = downloader.download_albumdee(
    "https://www.deezer.com/album/123456789",
    custom_dir_format="{artist}/{album} [{year}]"
)

# Example of custom track format
result = downloader.download_trackdee(
    "https://www.deezer.com/track/123456789",
    custom_track_format="{tracknumber} - {title}"
)
```

## License

This project is licensed under the GNU Affero General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Credits

This project is a fork of the [original deezspot library](https://github.com/jakiepari/deezspot).
