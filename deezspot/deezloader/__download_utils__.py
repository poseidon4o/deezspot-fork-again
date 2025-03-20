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
        data = f"{song_md5}{media_version}{song_id}"
        
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

def decrypt_blowfish_track(crypted_audio, song_id, md5_origin, song_path):
    """
    Decrypt the audio file using Blowfish encryption.
    
    Args:
        crypted_audio: The encrypted audio data
        song_id: The song ID for generating the key
        md5_origin: The MD5 hash of the track
        song_path: Path where to save the decrypted file
    """
    try:
        # Calculate the Blowfish key
        bf_key = __calcbfkey(song_id)
        
        # Approach 1: Collect all data first, then decrypt in proper blocks
        try:
            # Collect all encrypted data
            all_data = b''
            for chunk in crypted_audio:
                if chunk:
                    all_data += chunk
            
            # Ensure the total length is a multiple of 8 (Blowfish block size)
            block_size = 8
            if len(all_data) % block_size != 0:
                padding_size = block_size - (len(all_data) % block_size)
                all_data += b'\x00' * padding_size
                logger.debug(f"Added {padding_size} bytes of padding to make data a multiple of 8 bytes")
            
            # Create Blowfish cipher
            cipher = __newBlowfish(bf_key.encode(), __MODE_CBC, __idk)
            
            # Decrypt the data in properly sized chunks
            with open(song_path, 'wb') as f:
                for i in range(0, len(all_data), 2048):  # Use larger chunks for efficiency
                    chunk = all_data[i:i+2048]
                    # Ensure each chunk is a multiple of 8 bytes
                    if len(chunk) % block_size != 0:
                        padding_size = block_size - (len(chunk) % block_size)
                        chunk += b'\x00' * padding_size
                    decrypted_chunk = cipher.decrypt(chunk)
                    f.write(decrypted_chunk)
            
            logger.debug(f"Successfully decrypted and saved Blowfish-encrypted file to {song_path}")
            return
            
        except Exception as e:
            # If first approach fails, try alternate method
            logger.warning(f"First decryption approach failed: {e}. Trying alternate method...")
            
        # Approach 2: Process chunk by chunk with manual padding
        with open(song_path, 'wb') as f:
            buffer = b''
            cipher = __newBlowfish(bf_key.encode(), __MODE_CBC, __idk)
            
            for chunk in crypted_audio:
                if not chunk:
                    continue
                
                buffer += chunk
                
                # Process complete blocks of 8 bytes
                blocks_to_process = len(buffer) - (len(buffer) % 8)
                if blocks_to_process > 0:
                    data_to_decrypt = buffer[:blocks_to_process]
                    buffer = buffer[blocks_to_process:]
                    
                    decrypted_data = cipher.decrypt(data_to_decrypt)
                    f.write(decrypted_data)
            
            # Process any remaining data with padding
            if buffer:
                padding_size = 8 - (len(buffer) % 8)
                buffer += b'\x00' * padding_size
                decrypted_data = cipher.decrypt(buffer)
                f.write(decrypted_data)
                
        logger.debug(f"Successfully decrypted and saved Blowfish-encrypted file using alternate method to {song_path}")
        
    except Exception as e:
        logger.error(f"Failed to decrypt Blowfish file: {str(e)}")
        raise

def decryptfile(crypted_audio, ids, song_path):
    """
    Decrypt the audio file using either AES or Blowfish encryption.
    
    Args:
        crypted_audio: The encrypted audio data
        ids: The track IDs containing encryption info
        song_path: Path where to save the decrypted file
    """
    try:
        # Check encryption type
        encryption_type = ids.get('encryption_type', 'aes')
        
        if encryption_type == 'aes':
            # Get the AES encryption key and nonce
            key = bytes.fromhex(ids['key'])
            nonce = bytes.fromhex(ids['nonce'])
            
            # Create AES cipher in CTR mode
            cipher = AES.new(key, AES.MODE_CTR, counter=Counter.new(128, initial_value=int.from_bytes(nonce, byteorder='big')))
            
            # Decrypt and write the file
            with open(song_path, 'wb') as f:
                for chunk in crypted_audio:
                    if chunk:
                        decrypted_chunk = cipher.decrypt(chunk)
                        f.write(decrypted_chunk)
                        
            logger.debug(f"Successfully decrypted and saved AES-encrypted file to {song_path}")
            
        elif encryption_type == 'blowfish':
            # Use Blowfish decryption
            decrypt_blowfish_track(
                crypted_audio, 
                str(ids['track_id']), 
                ids['md5_origin'], 
                song_path
            )
        else:
            raise ValueError(f"Unknown encryption type: {encryption_type}")
            
    except Exception as e:
        logger.error(f"Failed to decrypt file: {str(e)}")
        raise