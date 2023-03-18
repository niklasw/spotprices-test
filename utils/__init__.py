from datetime import datetime
from pathlib import Path
import json
import sys


def log(msg):
    time = datetime.now().strftime('%Y%m%d-%H:%M:%S')
    print(f'{time:30s} {msg}')
    sys.stdout.flush()


def err(msg, x=1):
    time = datetime.now().strftime('%Y%m%d-%H:%M:%S')
    print(f'{time:30s} {msg}')
    sys.exit(x)


def file_age(file_path: Path):
    if file_path.exists():
        st_mtime = file_path.stat().st_mtime
    else:
        st_mtime = 0
    return datetime.now() - datetime.fromtimestamp(st_mtime)


class config(dict):

    def __init__(self, json_file):
        super().__init__(json.load(json_file))
        self.server = self['server']
        self.sources = self['sources']

    @classmethod
    def inv(cls, d):
        return {v: k for k, v in d.items()}


def dict_fetch(d: dict, *args):
    """Simplify deep probes in dict, like fetch_dict(d,'a','b','c')
    """
    rv = d
    for k in args:
        rv = rv[k]
    return rv


def test():
    CONFIG = config(open('config/sensors.json'))
    print(CONFIG.sources)
    print(CONFIG.inv(CONFIG.sources.w1))


def test_sensors():
    from utils import sensors
    sensors.test()


def test_prices():
    from utils import spot_price
    spot_price.test()
