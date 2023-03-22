from pathlib import Path
import re
from util.enums import ModSince, OnMatch, get_mod_enum, get_on_match_enum
import json
from requests import get
from time import time, sleep


class Thread:

    def __init__(self, board, post_id):
        self._board = board
        self._id = post_id
        self._cached_file = Thread.cache_path / \
            f'{self._board}:{self._id}.json'
        self._structure_info = {'board': self._board, 'thread': self._id}

    def _gen_path(self):
        op = self._data['posts'][0]
        if 'sub' in op.keys():
            self._structure_info['title'] = op['sub']
        elif 'com' in op.keys():
            end = len(op['com']) - 1
            if end > 15:
                end = 15
            self._structure_info['title'] = op['com'][end]
        else:
            self._structure_info['title'] = self._structure_info['thread']

        template = Thread.structure.lower()
        for t in ['board', 'thread', 'title']:
            (template, _) = re.subn(r'\%\(' + t + r'\)',
                                    self._structure_info[t], template)
        self._path = template

    def download(self):
        self._get_json_data()
        if self._data is None:
            return

        self._gen_path()

        self._get_files()

        if (len(self._files) == 0):
            print('Nothing to download')
        else:
            self._download_files()
        if Thread.clean:
            # Delete the cache file if archived
            try:
                if self._data['posts'][0]['closed'] == 1:
                    self._cached_file.unlink()
            except KeyError:
                pass

    def _download_files(self):
        container = Path(self._files[0]['path'].parent)
        container.mkdir(parents=True, exist_ok=True)
        succ = 0
        errs = 0
        count = len(self._files)

        for index, f in enumerate(self._files):
            api_url = f'https://i.4cdn.org/{self._board}/{f["file"]}'
            print(f'[{index + 1}/{count}] Fetching: {api_url}')
            start_time = time()
            resp = get(api_url, stream=True)
            if resp.status_code == 200:
                print(f'Saving to {str(f["path"])}')
                with f['path'].open(mode='wb') as outfile:
                    for chunk in resp.iter_content(4096):
                        outfile.write(chunk)
                succ += 1
            else:
                errs += 1
            end_time = time()
            elapsed = end_time - start_time
            if elapsed < 1:
                sleep(1 - elapsed)
        return (succ, errs)

    def _get_files(self):
        posts = self._data['posts']

        self._files = []

        if Thread.reverse:
            i = len(posts) - 1
            length = -1
            inc = -1
        else:
            length = len(posts)
            i = 0
            inc = 1

        while i != length:
            if 'filename' in posts[i].keys():

                fpath = Path(Thread.path) / self._gen_full_path(posts[i])
                if fpath.exists():
                    match Thread.on_match:
                        case OnMatch.APPEND:
                            counter = 1
                            while fpath.exists():
                                fpath = Path(
                                    fpath.parents[0] / f'{fpath.stem}({counter}){fpath.suffixes}')
                            self._files.append({
                                'path': fpath, 'file': f'{posts[i]["tim"]}{posts[i]["ext"]}'})
                        case OnMatch.REPLACE:
                            self._files.append(
                                {'path': fpath, 'file': f'{posts[i]["tim"]}{posts[i]["ext"]}'})
                        case OnMatch.SKIP:
                            pass
                        case OnMatch.STOP:
                            return
                else:
                    self._files.append(
                        {'path': fpath, 'file': f'{posts[i]["tim"]}{posts[i]["ext"]}'})
            i = i + inc

    def _gen_full_path(self, post):
        temp = self._path
        for t in [('id', 'tim'), ('post', 'no'), ('file', 'filename'), ('ext', 'ext')]:
            (temp, _) = re.subn(
                r'\%\(' + t[0] + r'\)', str(post[t[1]]), temp)
        return ''.join([temp, post['ext']])

    def _get_json_data(self):
        api_url = f'https://a.4cdn.org/{self._board}/thread/{self._id}.json'
        header_dict = dict()
        cached_data = None
        if self._cached_file.exists() and Thread.modified_since != ModSince.IGNORE:
            cached_data = json.loads(self._cached_file.read_bytes())
            header_dict['If-Modified-Since'] = cached_data['LastModified']
        resp = get(api_url, headers=header_dict)
        if resp.status_code == 200 and resp.headers['content-type'] == 'application/json':
            new_cache = {
                'LastModified': resp.headers['Last-Modified'],
                'json': resp.json()
            }
            self._cached_file.write_text(json.dumps(new_cache))
            self._data = new_cache['json']
        elif resp.status_code == 304 and Thread.modified_since == ModSince.REUSE and cached_data is not None:
            self._data = cached_data['json']
        else:
            self._data = None

    @staticmethod
    def from_url(url):
        match = re.search(r'boards\.4chan(?:nel)?\.org/(.+)/thread/(\d+)', url)
        if match is not None:
            return Thread(match.group(1), match.group(2))
        else:
            return None

    @staticmethod
    def set_args(clean, reverse, path, structure, cache_path, modified_since, on_match):
        Thread.clean = clean
        Thread.reverse = reverse
        Thread.path = path
        Thread.structure = structure
        Thread.cache_path = Path(cache_path).expanduser()
        Thread.modified_since = get_mod_enum(modified_since)
        Thread.on_match = get_on_match_enum(on_match)
