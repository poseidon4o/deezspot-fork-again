#!/usr/bin/python3

from hashlib import md5 as __md5

from binascii import (
	a2b_hex as __a2b_hex,
	b2a_hex as __b2a_hex
)

from Crypto.Cipher.Blowfish import (
	new as __newBlowfish,
	MODE_CBC as __MODE_CBC
)

from Crypto.Cipher import AES
from Crypto.Util import Counter
import os
from deezspot.libutils.logging_utils import logger

__secret_key = "g4el58wc0zvf9na1"
__secret_key2 = b"jo6aey6haid2Teih"
__idk = __a2b_hex("0001020304050607")

def md5hex(data: str):
	hashed = __md5(
		data.encode()
	).hexdigest()

	return hashed

def gen_song_hash(song_id, song_md5, media_version):
    """
    Generate a hash for the song using its ID, MD5 and media version.
    
    Args:
        song_id: The song's ID
        song_md5: The song's MD5 hash
        media_version: The media version
        
    Returns:
        str: The generated hash
    """
    try:
        # Combine the song data
        data = f"{song_id}{song_md5}{media_version}"
        
        # Generate hash using SHA1
        import hashlib
        hash_obj = hashlib.sha1()
        hash_obj.update(data.encode('utf-8'))
        return hash_obj.hexdigest()
        
    except Exception as e:
        logger.error(f"Failed to generate song hash: {str(e)}")
        raise

def __calcbfkey(songid):
	h = md5hex(songid)

	bfkey = "".join(
		chr(
			ord(h[i]) ^ ord(h[i + 16]) ^ ord(__secret_key[i])
		)

		for i in range(16)
	)

	return bfkey

def __blowfishDecrypt(data, key):
	c = __newBlowfish(
		key.encode(), __MODE_CBC, __idk	
	)

	return c.decrypt(data)

def decryptfile(crypted_audio, ids, song_path):
    """
    Decrypt the audio file using AES encryption.
    
    Args:
        crypted_audio: The encrypted audio data
        ids: The track IDs containing encryption key
        song_path: Path where to save the decrypted file
    """
    try:
        # Get the encryption key from the track IDs
        key = ids['key']
        nonce = ids['nonce']
        
        # Create AES cipher in CTR mode
        cipher = AES.new(key, AES.MODE_CTR, counter=Counter.new(128, initial_value=int.from_bytes(nonce, byteorder='big')))
        
        # Decrypt and write the file
        with open(song_path, 'wb') as f:
            for chunk in crypted_audio:
                if chunk:
                    decrypted_chunk = cipher.decrypt(chunk)
                    f.write(decrypted_chunk)
                    
        logger.debug(f"Successfully decrypted and saved file to {song_path}")
        
    except Exception as e:
        logger.error(f"Failed to decrypt file: {str(e)}")
        raise