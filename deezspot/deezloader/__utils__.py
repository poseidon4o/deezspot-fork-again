#!/usr/bin/python3

import json
import os
from deezspot.libutils.logging_utils import logger

def artist_sort(array: list):
	if len(array) > 1:
		for a in array:
			for b in array:
				if a in b and a != b:
					array.remove(b)

	array = list(
		dict.fromkeys(array)
	)

	artists = " & ".join(array)

	return artists

def check_track_token(infos_dw):
    """
    Check and extract track token from the Deezer API response.
    
    Args:
        infos_dw: Deezer API response data
        
    Returns:
        str: Track token
    """
    try:
        token = infos_dw.get('TRACK_TOKEN')
        if not token:
            logger.error("Missing TRACK_TOKEN in API response")
            raise ValueError("Missing TRACK_TOKEN")
            
        return token
        
    except Exception as e:
        logger.error(f"Failed to check track token: {str(e)}")
        raise

def check_track_ids(infos_dw):
    """
    Check and extract track IDs from the Deezer API response.
    
    Args:
        infos_dw: Deezer API response data
        
    Returns:
        dict: Track IDs and encryption info
    """
    try:
        # Extract required IDs
        track_id = infos_dw.get('SNG_ID')
        if not track_id:
            logger.error("Missing SNG_ID in API response")
            raise ValueError("Missing SNG_ID")
            
        # Get encryption info
        key = infos_dw.get('MEDIA_KEY')
        nonce = infos_dw.get('MEDIA_NONCE')
        
        if not key or not nonce:
            logger.error("Missing encryption info in API response")
            raise ValueError("Missing encryption info")
            
        return {
            'track_id': track_id,
            'key': key,
            'nonce': nonce
        }
        
    except Exception as e:
        logger.error(f"Failed to check track IDs: {str(e)}")
        raise

def check_track_md5(infos_dw):
    """
    Check and extract track MD5 from the Deezer API response.
    
    Args:
        infos_dw: Deezer API response data
        
    Returns:
        str: Track MD5 hash
    """
    try:
        md5 = infos_dw.get('MD5_ORIGIN')
        if not md5:
            logger.error("Missing MD5_ORIGIN in API response")
            raise ValueError("Missing MD5_ORIGIN")
            
        return md5
        
    except Exception as e:
        logger.error(f"Failed to check track MD5: {str(e)}")
        raise

def set_path(song_metadata, output_dir, method_save):
    """
    Set the output path for a track based on metadata and save method.
    
    Args:
        song_metadata: Track metadata
        output_dir: Base output directory
        method_save: Save method (e.g., 'artist/album/track')
        
    Returns:
        str: Full output path
    """
    try:
        # Create base directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Build path based on method
        if method_save == 'artist/album/track':
            path = os.path.join(
                output_dir,
                song_metadata['artist'],
                song_metadata['album'],
                f"{song_metadata['music']}.mp3"
            )
        else:
            path = os.path.join(
                output_dir,
                f"{song_metadata['artist']} - {song_metadata['music']}.mp3"
            )
            
        # Create parent directories
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        return path
        
    except Exception as e:
        logger.error(f"Failed to set path: {str(e)}")
        raise

def trasform_sync_lyric(lyrics):
    """
    Transform synchronized lyrics into a standard format.
    
    Args:
        lyrics: Raw lyrics data
        
    Returns:
        str: Formatted lyrics
    """
    try:
        if not lyrics:
            return ""
            
        # Parse lyrics data
        data = json.loads(lyrics)
        
        # Format each line with timestamp
        formatted = []
        for line in data:
            timestamp = line.get('timestamp', 0)
            text = line.get('text', '')
            if text:
                formatted.append(f"[{timestamp}]{text}")
                
        return "\n".join(formatted)
        
    except Exception as e:
        logger.error(f"Failed to transform lyrics: {str(e)}")
        return ""