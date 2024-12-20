#!/usr/bin/env python3

from . import log
import json
import requests


class general_sensors:
    ok = True

    def __init__(self, conf: dict):
        self.device_map = conf.get('devices') or {}
        self.subscription_topic = conf.get('subscription')

    def update(self):
        return self.get_values()

    def get_values(self):
        """Must be imlemented by subclass"""
        raise NotImplementedError


class http_parsers:

    def __init__(self, url: str, name: str):
        self.url = url
        self.name = name
        self.headers = None

    def fetch_json(self) -> dict:
        json_response = {}
        try:
            r = requests.get(self.url, headers=self.headers)
        except Exception:
            r = None
            log(f'http_sensors requests exception for sensor {self.name}')
            log(f'with url = {self.url}')
        if r:
            if r.status_code == 200:
                try:
                    json_response = r.json()
                except Exception as e:
                    log(f'http_sensors exception for sensor {self.name}'
                        f'from {self.url}. {e}')
            else:
                log(f'http_sensors: Request error from {self.url} '
                    f'with status {r.status_code}')
        return json_response

    def get_data(self):
        result = None
        json_response = self.fetch_json()
        if json_response:
            parser = self.select()
            temp = parser(json_response)
            if temp:
                result = temp
            else:
                log(f'http_sensors parser returned nothing from {self.name}')
        return result

    def select(self):
        if 'smhi' in self.url:
            return self.smhi
        if 'minglarn' in self.url:
            return self.minglarn
        if 'apilayer' in self.url and 'exchangerates' in self.url:
            return self.apilayer_exchange

    @staticmethod
    def apilayer_exchange(json_dict):
        # base_currency = json_dict.get('base')
        rates = json_dict.get('rates')
        if rates:
            return rates.get('SEK')

    @staticmethod
    def minglarn(json_dict):
        for tname in ('temperature', 'temp', 'temp:'):
            if tname in json_dict:
                return json_dict[tname]

    @staticmethod
    def smhi(json_dict):
        if values := json_dict.get('value'):
            if isinstance(values, list) and len(values):
                sample = values[-1]
                try:
                    return float(sample['value'])
                except ValueError:
                    log(f'http_parsers.smhi failed to parse one item {sample}')
