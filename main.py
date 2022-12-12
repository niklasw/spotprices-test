#!/usr/bin/env python3

from utils import config
from utils.sensors import mqtt_sensors
from utils.spot_price import mqtt_spot_price
from threading import Thread


with open('config/spot_price.json') as cf:
    conf1 = config(cf)
spot_price = mqtt_spot_price(conf1)
t1 = Thread(target=spot_price.run,
            daemon=True,
            name='spot_price_client')
t1.start()

with open('config/sensors.json') as cf:
    conf2 = config(cf)
sensors = mqtt_sensors(conf2)
t2 = Thread(target=sensors.run,
            daemon=True,
            name='tsensors_client')
t2.start()

t1.join()
t2.join()
