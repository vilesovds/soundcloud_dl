# -*- coding: utf-8 -*-
"""
To download all tracks with link like this https://soundcloud.com/7wy7q64hor8k/likes
with user likes.
based on https://github.com/captainmoha/SoundCloud-playlist-Downloader/blob/master/script.py
and
https://github.com/Miserlou/SoundScrape
"""
import soundcloud
import requests
from urllib import parse
import sys
from clint.textui import colored, puts, progress
import re
import os
from os.path import exists, join
from os import mkdir
from mutagen.mp3 import MP3, EasyMP3
from mutagen.id3 import APIC, WXXX
from mutagen.id3 import ID3 as OldID3


# client id from registered app YOU HAVE TO GET YOUR OWN FROM SOUNDCLOUD
CLIENT_ID = "b137996e08ffa19401924bd787ba8470"


def create_client(client_id=CLIENT_ID):
    # create client instance
    client = soundcloud.Client(client_id=client_id)
    return client


def puts_safe(text):
    if sys.platform == "win32":
        if sys.version_info < (3, 0, 0):
            puts(text)
        else:
            puts(text.encode(sys.stdout.encoding, errors='replace').decode())
    else:
        puts(text)


def tag_file(filename, artist, title, year=None, genre=None, artwork_url=None, album=None, track_number=None, url=None):
    """
    Attempt to put ID3 tags on a file.

    Args:
        artist (str):
        title (str):
        year (int):
        genre (str):
        artwork_url (str):
        album (str):
        track_number (str):
        filename (str):
        url (str):
    """

    try:
        audio = EasyMP3(filename)
        audio.tags = None
        audio["artist"] = artist
        audio["title"] = title
        if year:
            audio["date"] = str(year)
        if album:
            audio["album"] = album
        if track_number:
            audio["tracknumber"] = track_number
        if genre:
            audio["genre"] = genre
        if url:  # saves the tag as WOAR
            audio["website"] = url
        audio.save()

        if artwork_url:

            artwork_url = artwork_url.replace('https', 'http')

            mime = 'image/jpeg'
            if '.jpg' in artwork_url:
                mime = 'image/jpeg'
            if '.png' in artwork_url:
                mime = 'image/png'

            if '-large' in artwork_url:
                new_artwork_url = artwork_url.replace('-large', '-t500x500')
                try:
                    image_data = requests.get(new_artwork_url).content
                except Exception as e:
                    # No very large image available.
                    image_data = requests.get(artwork_url).content
            else:
                image_data = requests.get(artwork_url).content

            audio = MP3(filename, ID3=OldID3)
            audio.tags.add(
                APIC(
                    encoding=3,  # 3 is for utf-8
                    mime=mime,
                    type=3,  # 3 is for the cover image
                    desc='Cover',
                    data=image_data
                )
            )
            audio.save()

        # because there is software that doesn't seem to use WOAR we save url tag again as WXXX
        if url:
            audio = MP3(filename, ID3=OldID3)
            audio.tags.add(WXXX(encoding=3, url=url))
            audio.save()

        return True

    except Exception as e:
        puts(colored.red("Problem tagging file: ") + colored.white("Is this file a WAV?"))
        return False


def sanitize_filename(filename):
    """
    Make sure filenames are valid paths.

    Returns:
        str:
    """
    sanitized_filename = re.sub(r'[/\\:*?"<>|]', '-', filename)
    sanitized_filename = sanitized_filename.replace('&', 'and')
    sanitized_filename = sanitized_filename.replace('"', '')
    sanitized_filename = sanitized_filename.replace("'", '')
    sanitized_filename = sanitized_filename.replace("/", '')
    sanitized_filename = sanitized_filename.replace("\\", '')

    # Annoying.
    if sanitized_filename[0] == '.':
        sanitized_filename = u'dot' + sanitized_filename[1:]

    return sanitized_filename


def download_file(url, path, session=None, params=None):
    """
    Download an individual file.
    """

    if url[0:2] == '//':
        url = 'https://' + url[2:]

    # Use a temporary file so that we don't import incomplete files.
    tmp_path = path + '.tmp'

    if session and params:
        r = session.get(url, params=params, stream=True)
    elif session and not params:
        r = session.get(url, stream=True)
    else:
        r = requests.get(url, stream=True)
    with open(tmp_path, 'wb') as f:
        total_length = int(r.headers.get('content-length', 0))
        for chunk in progress.bar(r.iter_content(chunk_size=1024), expected_size=(total_length / 1024) + 1):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()

    os.rename(tmp_path, path)

    return path


def download_tracks(client, tracks, num_tracks=sys.maxsize, downloadable=False,
                    folders=False, custom_path='', id3_extras={}):
    """
    Given a list of tracks, iteratively download all of them.

    """

    filenames = []

    for i, track in enumerate(tracks):

        # "Track" and "Resource" objects are actually different,
        # even though they're the same.
        if isinstance(track, soundcloud.resource.Resource):

            try:
                t_track = {}
                t_track['downloadable'] = track.downloadable
                t_track['streamable'] = track.streamable
                t_track['title'] = track.title
                t_track['user'] = {'username': track.user['username']}
                t_track['release_year'] = track.release
                t_track['genre'] = track.genre
                t_track['artwork_url'] = track.artwork_url
                if track.downloadable:
                    t_track['stream_url'] = track.download_url
                else:
                    if downloadable:
                        puts_safe(colored.red("Skipping") + colored.white(": " + track.title))
                        continue
                    if hasattr(track, 'stream_url'):
                        t_track['stream_url'] = track.stream_url

                track = t_track
            except Exception as e:
                puts_safe(colored.white(track.title) + colored.red(' is not downloadable.'))
                continue

        if i > num_tracks - 1:
            continue
        try:
            if not track.get('stream_url', False):
                puts_safe(colored.white(track['title']) + colored.red(' is not downloadable.'))
                continue
            else:
                track_artist = sanitize_filename(track['user']['username'])
                track_title = sanitize_filename(track['title'])
                track_filename = track_artist + ' - ' + track_title + '.mp3'

                if folders:
                    track_artist_path = join(custom_path, track_artist)
                    if not exists(track_artist_path):
                        mkdir(track_artist_path)
                    track_filename = join(track_artist_path, track_filename)
                else:
                    track_filename = join(custom_path, track_filename)

                if exists(track_filename):
                    puts_safe(colored.yellow("Track already downloaded: ") + colored.white(track_title))
                    continue

                puts_safe(colored.green("Downloading") + colored.white(": " + track['title']))

                if track.get('direct', False):
                    location = track['stream_url']
                else:
                    stream = client.get(track['stream_url'], allow_redirects=False, limit=200)
                    if hasattr(stream, 'location'):
                        location = stream.location
                    else:
                        location = stream.url

                filename = download_file(location, track_filename)
                tagged = tag_file(filename,
                                  artist=track['user']['username'],
                                  title=track['title'],
                                  year=track['release_year'],
                                  genre=track['genre'],
                                  album=id3_extras.get('album', None),
                                  artwork_url=track['artwork_url'])

                if not tagged:
                    wav_filename = filename[:-3] + 'wav'
                    os.rename(filename, wav_filename)
                    filename = wav_filename

                filenames.append(filename)
        except Exception as e:
            puts_safe(colored.red("Problem downloading ") + colored.white(track['title']))
            puts_safe(str(e))

    return filenames


def assure_folder_exists(root, folder):
    full_path = os.path.join(root, folder)
    if not os.path.isdir(full_path):
        os.mkdir(full_path)
    return full_path


def print_help():
    print('Usage:')
    print(f'python {sys.argv[0]} <url> [<path>]')
    print('url should be like this')
    print('https://soundcloud.com/7wy7q64hor8k/likes')


def main(url, download_dir=os.path.curdir):
    client = create_client()
    assure_folder_exists(os.getcwd(), download_dir)
    if 'likes' in url.lower():
        url = url[0:url.find('/likes')]
        user_id = str(client.get('/resolve', url=url).id)
        resolved = client.get('/users/' + user_id + '/favorites', limit=200, linked_partitioning=1)
        next_href = False
        if hasattr(resolved, 'next_href'):
            next_href = resolved.next_href

        while next_href:
            params = dict(parse.parse_qsl(parse.urlsplit(next_href).query))
            resolved2 = client.get('/users/' + user_id + '/favorites', **params)
            resolved.collection.extend(resolved2.collection)
            if hasattr(resolved2, 'next_href'):
                next_href = resolved2.next_href
            else:
                next_href = False
        tracks = resolved.collection
        download_tracks(client, tracks, len(tracks), custom_path=download_dir)
    else:
        print('Wrong url')
        print_help()
        exit(-1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print_help()
    elif len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        main(sys.argv[1], sys.argv[2])
