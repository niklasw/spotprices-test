#!/usr/bin/env python3

from utils import config
from utils.sensors import mqtt_sensor
from utils.spot_price import mqtt_spot_price
from threading import Thread


def run_threads():
    with open('config/sensors.json') as cf:
        conf = config(cf)
        spot_price = mqtt_spot_price(conf, 'entsoe')
        spot_price.exception_delay = 60

        p1 = Thread(target=spot_price.run,
                    daemon=True,
                    name='spot_price_client')

        w1_sensors = mqtt_sensor(conf, 'w1')
        http_sensors = mqtt_sensor(conf, 'http')
        w1_sensors.execution_delay = 60
        http_sensors.execution_delay = 5*60

        t1 = Thread(target=w1_sensors.run,
                    daemon=True,
                    name='w1_client')

        t2 = Thread(target=http_sensors.run,
                    daemon=True,
                    name='http_client')

    threads = [p1, t1, t2]

    for thread in threads:
        thread.start()

    print('Threads started')

    for thread in threads:
        thread.join()


run_threads()
