from datetime import datetime
from dotted_dict import DottedDict
import json
import sys


def log(msg):
    time = datetime.now().strftime('%Y%m%d-%H:%M:%S')
    print(f'{time:30s} {msg}')


def err(msg, x=1):
    time = datetime.now().strftime('%Y%m%d-%H:%M:%S')
    print(f'{time:30s} {msg}')
    sys.exit(x)


class config(DottedDict):

    def __init__(self, json_file):
        super().__init__(json.load(json_file))

    @classmethod
    def inv(cls, d):
        return {v: k for k, v in d.items()}


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
