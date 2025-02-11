#!/usr/bin/python3

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

def check_track_token(infos: dict):
	if "FALLBACK" in infos:
		track_token = infos['FALLBACK']['TRACK_TOKEN']
	else:
		track_token = infos['TRACK_TOKEN']

	return track_token

def check_track_ids(infos: dict) -> str:
    if "FALLBACK" in infos:
        if 'EPISODE_ID' in infos['FALLBACK']:
            return infos['FALLBACK']['EPISODE_ID']
        elif 'SNG_ID' in infos['FALLBACK']:
            return infos['FALLBACK']['SNG_ID']
    else:
        if 'EPISODE_ID' in infos:
            return infos['EPISODE_ID']
        elif 'SNG_ID' in infos:
            return infos['SNG_ID']
    
    raise ValueError("Track ID not found in the provided information")

def check_track_md5(infos: dict):
    if "FALLBACK" in infos:
        song_md5 = infos['FALLBACK']['MD5_ORIGIN']
        version = infos['FALLBACK']['MEDIA_VERSION'] if 'MEDIA_VERSION' in infos['FALLBACK'] else None
    else:
        song_md5 = infos['MD5_ORIGIN']
        version = infos['MEDIA_VERSION'] if 'MEDIA_VERSION' in infos else None

    return song_md5, version