#!/usr/bin/env python3

from . import log, config
import paho.mqtt.client as mqtt
from dataclasses import dataclass
import sys


@dataclass
class server_info:
    address: str = '192.168.10.200'
    port: int = 1883
    protocol: str = 'tcp'


@dataclass
class hass_topic:
    topic: str = '$SYS/#'
    retain: bool = False
    qos: int = 0

    def __repr__(self):
        return f'{self.topic}, retain = {self.retain}, QoS = {self.qos}'


class hass_client(mqtt.Client):
    debug = False

    def __init__(self):
        super().__init__()
        self.server = server_info()
        self.topics: dict = {'sys': hass_topic(),
                             'available': hass_topic(topic='$SYS/available'),
                             'pub': None}
        self.QoS: int = 1

    def connect(self):
        try:
            super().connect(self.server.address, self.server.port,
                            keepalive=60)
        except Exception:
            log('Can not connect to mqtt server.')
            sys.exit(1)
        self.pub('available', 'online')

    def on_connect(self, client, userdata, flags, rc):
        log(f'Connected. Result code {str(rc)}')

    def on_disconnect(self, client, userdata, rc):
        log(f'Disconnecting. Result code {str(rc)}')

    def on_message(self, client, userdata, msg):
        log(f'Got message regarding {msg.topic} - {msg.payload}')

    def pub(self, topic_name, payload):
        topic = self.topics[topic_name]
        self.publish(topic.topic,
                     payload=payload,
                     qos=topic.qos,
                     retain=topic.retain)

    def disconnect(self):
        self.pub('available', 'offline')
        self.loop_stop()
        super().disconnect()

    def loop(self):
        super().loop_forever()


class mqtt_publisher:

    exception_delay = 5*60
    execution_delay = 5*60

    def __init__(self, conf: config):
        self.client = hass_client()
        self.client.server = server_info(**conf.server)
        for topic, value in conf.topics.items():
            self.client.topics[topic] = hass_topic(**value)
        log(self.client.topics)

        self.sources = []

    def action(self):
        pass

    def run(self):
        self.client.connect()
        self.client.loop_start()
        while True:
            try:
                self.action()
            except (KeyboardInterrupt, SystemExit):
                self.offline()
                break
        self.client.loop_stop()
        self.client.disconnect()

    def offline(self):
        self.client.pub('available', 'offline')
