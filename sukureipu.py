"""
Downloads all images from a provided 4chan thread.

Usage:
    sukureipu [--verbose <LVL>]
              [--reverse]
              [--path <PATH>]
              [--structure <STRUCTURE>]
              [--cache <PATH>]
              [--modified-since <BEHAVIOR>]
              [--on-match <ACTION>]
              [--clean] (refresh [<BOARD> [<THREAD>]] | clean | <URL>...)

Options:
    -c, --clean                    Cleans archived threads after downloading
    -r, --reverse                  Begins the scrape with the latest post
    -p, --path PATH                PATH of directory to download to [default: .]
    -s, --structure STRUCTURE      The directory structure of downloads [default: %(BOARD)/%(THREAD)/%(ID)]
    -v, --verbose LVL              The verbosity of the output, determined by LVL [default: 1]
    --cache PATH                   The path to use as the cache directory [default: ~/.cache/sukureipu]
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
    - Extract out constants
    - MD5 Check
"""

import sys
from docopt import docopt
from schema import Schema, And, Or, SchemaError, Use
from Thread import Thread


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

    Thread.set_args(args['--clean'], args['--reverse'], args['--path'], args['--structure'],
                    args['--cache'], args['--modified-since'], args['--on-match'])

    if args['clean']:
        files = Thread.cache_path.glob('*')
        [f.unlink() for f in files]
        sys.exit()

    # board name, thread number
    threads = []
    if args['refresh']:
        if args['<BOARD>']:
            if args['<THREAD>']:
                threads.append(Thread(args['<BOARD>'], args['<THREAD>']))
            else:
                # Get all cached files that match board
                # Generate structure_info for all of them
                thread_params = [f.stem.split(':') for f in Thread.cache_path.iterdir(
                ) if f.stem.startswith(args['<BOARD>'])]
                for param in thread_params:
                    threads.append(Thread(param[0], param[1]))
        else:
            thread_params = [f.stem.split(':') for f in Thread.cache_path.iterdir(
            )]
            for param in thread_params:
                threads.append(Thread(param[0], param[1]))
    else:
        for url in args['<URL>']:
            if (t := Thread.from_url(url)) is not None:
                threads.append(t)
    for thread in threads:
        thread.download()


if __name__ == '__main__':
    main()
