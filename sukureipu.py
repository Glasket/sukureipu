"""
Downloads all images from a provided 4chan thread.

Usage:
    sukureipu [--verbose <LVL>]
              [--reverse]
              [--path <PATH>]
              [--structure <STRUCTURE>]
              [--modified-since <BEHAVIOR>]
              [--on-match <ACTION>] (refresh [<BOARD> [<THREAD>]] | <URL>)
    sukureipu --clean

Options:
    -c, --clean                    Cleans sukureipu's cache folder
    -r, --reverse                  Begins the scrape with the latest post
    -p, --path PATH                PATH of directory to download to [default: .]
    -s, --structure STRUCTURE      The directory structure of downloads [default: %(BOARD)/%(THREAD)/%(ID)]
    -v, --verbose LVL              The verbosity of the output, determined by LVL [default: 1]
    --modified-since BEHAVIOR      Sets the behavior around using if-modified-since [default: reuse]
    --on-match ACTION              Defines the behavior on finding an existing file [default: skip]

Structure Args:
    %(BOARD)      The board which the thread is from (g, wsr, a)
    %(THREAD)     The post id of the OP for the thread (first no)
    %(TITLE)      The title of the thread (sub)

    %(ID)         The image timestamp (tim)
    %(POST)       The post id (no)
    %(FILE)       The actual name of the uploaded file (filename)
    %(EXT)        The file extension

    TEXT        Any text which is not escaped with %() will be inserted as-is
    Extensions are automatically appended at the end

Modified Since:
    ignore      Doesn't use if-modified-since (not recommended, against API rules)
    reuse       Reuses the old JSON if the server JSON hasn't been modified
    stop        Stops if the if-modified-since request fails

On Match:
    append      Appends a counter to the end of the filename
    replace     Redownloads the file and overwrites the match
    skip        Do nothing
    stop        Stops the script when a match is found

Optimized Run:
    sukureipu -r --on-match stop --modified-since stop <URL>
    Useful for scraping a thread multiple times when checking for files

Plans:
    - Config file
    - File extension filtering
    - Better structure
    - Add 'refresh' that can take in a cache file rather than a url
    - Extract out constants
    - MD5 Check
"""

from time import time, sleep
import requests
import re
import json
from pathlib import Path
import sys
from docopt import docopt
from schema import Schema, And, Or, SchemaError, Use
from util.enums import get_on_match_enum, get_mod_enum, ModSince, OnMatch
import util.globals as g
import logging


def download_files(file_objects, board):
    container = Path(file_objects[0]['path'].parent)
    container.mkdir(parents=True, exist_ok=True)
    succ = 0
    errs = 0
    count = len(file_objects)

    for index, f in enumerate(file_objects):
        api_url = f'https://i.4cdn.org/{board}/{f["file"]}'
        print(f'[{index + 1}/{count}] Fetching: {api_url}')
        start_time = time()
        resp = requests.get(api_url, stream=True)
        if resp.status_code == 200:
            print(f'Saving to {str(f["path"])}')
            with f['path'].open(mode='wb') as outfile:
                for chunk in resp.iter_content(4096):
                    outfile.write(chunk)
            succ += 1
        else:
            g.LOGGER.error(f'ERR: {resp.status_code}')
            errs += 1
        end_time = time()
        elapsed = end_time - start_time
        if elapsed < 1:
            sleep(1 - elapsed)
    return (succ, errs)


def gen_full_path(post, template):
    for t in [('id', 'time'), ('post', 'no'), ('file', 'filename'), ('ext', 'ext')]:
        (template, _) = re.subn(
            r'\%\(' + t[0] + r'\)', str(post[t[1]]), template)
    return ''.join([template, post['ext']])


def extract_file_objects(json_data, reverse, on_match, template, base_path):
    posts = json_data['posts']

    file_objs = []

    if reverse:
        i = len(posts) - 1
        length = -1
        inc = -1
    else:
        length = len(posts)
        i = 0
        inc = 1

    while i != length:
        if 'filename' in posts[i].keys():
            fpath = Path(base_path) / gen_full_path(posts[i], template)
            if fpath.exists():
                match on_match:
                    case OnMatch.APPEND:
                        counter = 1
                        while fpath.exists():
                            fpath = Path(
                                fpath.parents[0] / f'{fpath.stem}({counter}){fpath.suffixes}')
                        file_objs.append({
                            'path': fpath, 'file': f'{posts[i]["tim"]}{posts[i]["ext"]}'})
                    case OnMatch.REPLACE:
                        file_objs.append(
                            {'path': fpath, 'file': f'{posts[i]["tim"]}{posts[i]["ext"]}'})
                    case OnMatch.SKIP:
                        pass
                    case OnMatch.STOP:
                        return file_objs
            else:
                file_objs.append(
                    {'path': fpath, 'file': f'{posts[i]["tim"]}{posts[i]["ext"]}'})
        i = i + inc
    return file_objs


def gen_path(structure_info, template):
    template = template.lower()
    for t in ['board', 'thread', 'title']:
        (template, _) = re.subn(r'\%\(' + t + r'\)',
                                structure_info[t], template)
    return template


def get_json_data_for_thread(url_info, cached_file, modified_since):
    api_url = f'https://a.4cdn.org/{url_info["board"]}/thread/{url_info["thread"]}.json'
    header_dict = dict()
    cached_data = None
    if cached_file is not None and modified_since != ModSince.IGNORE:
        cached_data = json.loads(cached_file.read_bytes())
        header_dict['If-Modified-Since'] = cached_data['LastModified']
    resp = requests.get(api_url, headers=header_dict)
    if resp.status_code == 200 and resp.headers['content-type'] == 'application/json':
        cache_file = g.CACHE / f'{url_info["board"]}:{url_info["thread"]}.json'
        new_cache = {
            'LastModified': resp.headers['Last-Modified'],
            'json': resp.json()
        }
        cache_file.write_text(json.dumps(new_cache))
        return new_cache['json']
    elif resp.status_code == 304 and modified_since == ModSince.REUSE and cached_data is not None:
        return cached_data['json']
    else:
        g.LOGGER.info('Early exit')
        sys.exit(0)


def get_cached_file(url_info):
    cached_file = g.CACHE / \
        f'{url_info["board"]}:{url_info["thread"]}.json'
    if cached_file.exists():
        return cached_file
    else:
        return None


def parse_url(url):
    match = re.search(r'boards\.4chan\.org/(.+)/thread/(\d+)', url)
    if match is not None:
        return {
            'board': match.group(1),
            'thread': match.group(2)
        }
    else:
        g.LOGGER.error(
            'URL is invalid: Could not detect pattern \'boards.4chan.org/BOARD/thread/ID')
        sys.exit(64)


def main():
    args = docopt(__doc__)
    schema = Schema({
        '--modified-since': Or('reuse', 'ignore', 'stop', error='--modified-since must be "reuse", "ignore", or "stop"'),
        '--on-match': Or('append', 'replace', 'skip', 'stop', error='--on-match must be "append", "replace", "skip", or "stop"'),
        '--verbose': And(Use(int), lambda n: 0 <= n <= 3)
    }, ignore_extra_keys=True)

    try:
        schema.validate(args)
    except SchemaError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    if args['--clean']:
        files = g.CACHE.glob('*')
        [f.unlink() for f in files]
    else:
        match args['--verbose']:
            case 0:
                g.SUK_LOGGER.setLevel(logging.ERROR)
            case 1:
                g.SUK_LOGGER.setLevel(logging.WARNING)
            case 2:
                g.SUK_LOGGER.setLevel(logging.INFO)
            case 3:
                g.SUK_LOGGER.setLevel(logging.DEBUG)
        mod_since = get_mod_enum(args['--modified-since'])
        on_match = get_on_match_enum(args['--on-match'])
        # board name, thread number
        structure_info = parse_url(args['<URL>'])

        json_data = get_json_data_for_thread(structure_info, get_cached_file(
            structure_info), mod_since)

        op = json_data['posts'][0]
        if 'sub' in op.keys():
            structure_info['title'] = op['sub']
        elif 'com' in op.keys():
            end = len(op['com']) - 1
            if end > 15:
                end = 15
            structure_info['title'] = op['com'][end]
        else:
            structure_info['title'] = structure_info['thread']

        path_str = gen_path(
            structure_info, args['--structure'])

        file_info = extract_file_objects(
            json_data, args['--reverse'], on_match, path_str, args['--path'])

        if (len(file_info) == 0):
            print('Nothing to download')
            sys.exit()
        res = download_files(file_info, structure_info['board'])

        print(
            f'Finished. {res[0]} files successfully downloaded. {res[1]} files failed.')


if __name__ == '__main__':
    main()
