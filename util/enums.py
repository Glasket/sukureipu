from enum import Enum
from pickle import APPEND


class ModSince(Enum):
    REUSE = 1
    STOP = 2
    IGNORE = 3


class OnMatch(Enum):
    APPEND = 1
    REPLACE = 2
    SKIP = 3
    STOP = 4


def get_mod_enum(mod_since):
    match mod_since:
        case 'reuse':
            return ModSince.REUSE
        case 'stop':
            return ModSince.STOP
        case 'ignore':
            return ModSince.IGNORE


def get_on_match_enum(on_match):
    match on_match:
        case 'append':
            return OnMatch.APPEND
        case 'replace':
            return OnMatch.REPLACE
        case 'skip':
            return OnMatch.SKIP
        case 'STOP':
            return OnMatch.STOP
