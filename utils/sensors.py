#!/usr/bin/env python3

from . import log, config
from .mqtt_client import mqtt_publisher
import json

from .temperature import http_sensors, w1_sensors
from .spot_price import entsoe_price_list


class mqtt_sensor(mqtt_publisher):

    def __init__(self, conf: config, name: str):
        super().__init__(conf)
        self.name = name
        self.read(name)
        sensor_class = globals()[self.type_name]
        self.sensor = sensor_class(self.type_conf)

    def sensor_ok(self):
        return self.sensor.ok

    def action(self):
        try:
            result = self.sensor.update()
        except Exception as e:
            result = {}
            log(e)
            log('Exception in mqtt_sensor action')
        if result:
            self.pub('available', 'online')
            self.pub('pub', json.dumps(result))
            log(json.dumps(result))
            return True
        else:
            self.pub('available', 'offline')
            log(f'{self.name} sensor offline')
            return False


def test():
    CONFIG = config(open('config/sensors.json'))
    worker1 = mqtt_sensor(CONFIG, 'entsoe')
    worker1.run()
