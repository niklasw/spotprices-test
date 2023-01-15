#!/usr/bin/env python3

from . import log, config
from .mqtt_client import mqtt_publisher
import json
import requests

try:
    from w1thermsensor import W1ThermSensor
    W1_SENSORS_OK = True
except Exception as e:
    W1_SENSORS_OK = False
    log(e)


class MyTemperatureException(Exception):
    def __init__(self, message='Temperature exception raised'):
        super().__init__(message=message)


class temperature_sensors:

    def __init__(self, conf: dict):
        self.device_map = conf

    def update(self):
        return self.get_temperatures()

    def get_temperature(self):
        return {}

    def json(self):
        return json.dumps(self.get_temperatures())


class http_sensors(temperature_sensors):

    def __init__(self, conf: dict):
        super().__init__(conf)
        self.parser = self.parse_temperature

    def parse_temperature(self, json_dict: dict):
        for tname in ('temperature', 'temp', 'temp:'):
            if tname in json_dict:
                return json_dict[tname]

    def get_temperatures(self):
        result = {}
        for url, name in self.device_map.items():
            try:
                r = requests.get(url)
            except Exception:
                log(f'http_sensors requests exception for sensor {name}')
                log(f'with url = {url}')
                continue
            if r.status_code == 200:
                try:
                    json_response = r.json()
                except Exception as e:
                    log(f'http_sensors error for sensor {name}'
                        f'from {url}. {e}')
                    continue
                temp = self.parser(json_response)
                if temp:
                    result[name] = temp
            else:
                log(f'http_sensors: Request error from {url} '
                    f'with status {r.status_code}')
        return result


class w1_sensors(temperature_sensors):

    def __init__(self, conf: dict):
        super().__init__(conf)
        self.kernel_ok = W1_SENSORS_OK

    def get_temperatures(self):
        result = {}
        if self.kernel_ok:
            for s in W1ThermSensor.get_available_sensors():
                if s.id in self.device_map:
                    name = self.device_map[s.id]
                    try:
                        result[name] = s.get_temperature()
                    except Exception:
                        log(f'w1_sensors exception for sensor {name}')
        else:
            log('No w1_sensors result since kernel modules fails')
        return result


class mqtt_sensor(mqtt_publisher):

    def __init__(self, conf: config, name: str):
        super().__init__(conf)
        self.read(name)
        sensor_class = globals()[self.type_name]
        self.sensor = sensor_class(self.type_conf)

    def action(self):
        result = {}
        result = {**result, **(self.sensor.update())}
        if result:
            self.pub('available', 'online')
            self.pub('pub', json.dumps(result))
            log(json.dumps(result))
            return True
        else:
            self.pub('available', 'offline')
            log('temperature sensors offline')
            return False


def test():
    CONFIG = config(open('config/sensors.json'))
    worker1 = mqtt_sensor(CONFIG, 'http')
    worker1.run()
