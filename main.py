#!/usr/bin/env python3

from utils.sensors import run_tsensors
from utils.spot_price import run_client
from threading import Thread


if __name__ == '__main__':

    Thread(target=run_client,
           daemon=True,
           name='mqtt_price_client').start()

    Thread(target=run_tsensors,
           daemon=True,
           name='tsensors_client').run()
