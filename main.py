#!/usr/bin/env python3

from utils import config
from threading import Thread
from utils.mqtt_client import mqtt_sensor
import os


def my_import(name):
    components = name.split('.')
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def run_sensors():
    threads = []
    with open('config/sensors.json') as cf:
        conf = config(cf)
        for name in conf.sources:
            actor = mqtt_sensor(conf, name)
            if not actor.disabled and actor.sensor_ok():
                thread = Thread(target=actor.run,
                                daemon=True,
                                name=f'{name}_thread')
                threads.append(thread)

    for thread in threads:
        print(f'Starting thread {thread.name}')
        thread.start()

    print('Threads started')

    for thread in threads:
        thread.join()


print(f'PID: {os.getpid()}')
run_sensors()
