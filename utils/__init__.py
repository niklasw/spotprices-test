from datetime import datetime
import json


def log(msg):
    time = datetime.now().strftime('%Y%m%d-%H:%M:%S')
    print(f'{time:30s} {msg}')


class config(dict):

    def __init__(self, json_file):
        super().__init__(json.load(json_file))
        self.sensors: dict = self['sensors']
        self.topics: dict = self['topics']
        self.server: dict = self['server']

    @classmethod
    def inv(cls, d):
        return {v: k for k, v in d.items()}
