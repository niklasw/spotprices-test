#!/usr/bin/env python3

from utils import config
from utils.sensors import mqtt_sensors
from utils.spot_price import run_client
from threading import Thread


if __name__ == '__main__':

    Thread(target=run_client,
           daemon=True,
           name='mqtt_price_client').start()

    with open('config/sensors.json') as cf:
        sensor_config = config(cf)
        sensors = mqtt_sensors(sensor_config)
        Thread(target=sensors.run,
               daemon=True,
               name='tsensors_client').run()
