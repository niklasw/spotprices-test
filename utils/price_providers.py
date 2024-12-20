#!/usr/bin/env python3

import requests
import json
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import parser
import pytz
import pandas as pd
from . import log, err


class SpotpriceRequest:
    TIME_ZONE = 'Europe/Stockholm'
    TZ = pytz.timezone(TIME_ZONE)
    time_fmt = "%Y-%m-%dT%H:%M:%S"  # "2023-05-29T11:00:00"
    region = 'SE3'
    url = None

    def __init__(self):
        log('SpotpriceRequest instantiated')
        self.price_list: pd.Series = None

    def request(self, from_file: Path = None):
        log('SpotpriceRequest requesting new data')
        try:
            r = requests.get(self.url, timeout=5)
        except:
            return None
        if not r.status_code == 200:
            info = {'error': 'status',
                    'from': 'SpotpriceRequest',
                    'status': r.status_code}
            log(json.dumps(info))
            return None
        else:
            try:
                data = r.json()
            except requests.RequestException as e:
                info = {'error': 'json_data',
                        'json_data': str(e)}
                log(json.dumps(info))
                return None
        return data

    def parse_data():
        log('parse_data cannot be used by the base class')
        sys.exit(1)

    def fetch_prices(self):
        self.parse_data(self.request())
        return self.price_list


class Elprisetjustnu(SpotpriceRequest):
    """
    request delivers json as a list of elements like:
    {
      "SEK_per_kWh": 1.10534,
      "EUR_per_kWh": 0.0979,
      "EXR": 11.290508,
      "time_start": "2023-12-07T20:00:00+01:00",
      "time_end": "2023-12-07T21:00:00+01:00"
    }
    URL path is on format
    https://www.elprisetjustnu.se/api/v1/prices/2023/12-07_SE3.json
    """
    base_url = "https://www.elprisetjustnu.se/api/v1/prices"

    def __init__(self, when=datetime.now()):
        super().__init__()
        path=when.strftime(f'%Y/%m-%d_{self.region}.json')
        self.url = self.make_url(when)
        log(f'Elprisetjustnu instantiated with url = {self.url}')

    def make_url(self, when=datetime.now()):
        path=when.strftime(f'%Y/%m-%d_{self.region}.json')
        return f'{self.base_url}/{path}'

    def parse_data(self, data: list = None):
        if not data:
            return
        price_list = pd.Series(dtype='float64')
        if isinstance(data, list):
            for item in data:
                try:
                    sek = float(item.get('SEK_per_kWh'))
                except:
                    log('Elprisetjustnu parse value error')
                    sek = None
                time_str = item.get('time_start')
                try:
                    time = parser.parse(time_str)
                except:
                    log('Elprisetjustnu parse time error')
                    time = None

                if sek and time:
                    price_list[time] = sek*100
        else:
            raise(ValueError)
        return price_list

    def fetch_prices(self):
        """Overloading fetch_prices, since this service requires a double
        request to get tomorrows data when available"""
        self.url = self.make_url(datetime.now())
        p1 = self.parse_data(self.request())
        self.url = self.make_url(datetime.now()+timedelta(days=1))
        p2 = self.parse_data(self.request())
        self.price_list = pd.concat([p1, p2], axis=0)
        return self.price_list



class Nordpool(SpotpriceRequest):
    """Deprecated. The API url seems outdated"""
    url = "https://www.nordpoolgroup.com/api/marketdata/page/10"
    url += "?currency=SEK,SEK,SEK,SEK"

    def __init__(self):
        print('Unavailable API from Nordpool')
        sys.exit(1)
        super().__init__()

    def parse_data(self, data: dict):
        if not data:
            return
        if self.price_list is None:
            self.price_list = pd.Series(dtype='float64')
        rows = data.get('data').get('Rows')
        for row in rows:
            if 'Columns' in row.keys():
                time_string = row.get('StartTime')
                measurementName = row.get('Name')
                if time_string and '&' in measurementName:
                    time = self.TZ.localize(parser.parse(time_string))
                    for cell in row.get('Columns'):
                        if cell.get('Name') == self.region:
                            try:
                                cell_str = cell['Value'].replace(',', '.')
                                cell_str = cell_str.replace(' ', '')
                                price = float(cell_str)/10.0 # data in kr/MWh
                            except ValueError as e:
                                price = None
                                print('Could not read price Value')
                                print(e)
                            self.price_list[time] = price


def main(plot=False):
    service = Nordpool()
    prices = service.fetch_prices()

    service2 = Elprisetjustnu()
    prices2 = service2.fetch_prices()
    service2 = Elprisetjustnu(datetime.now()+timedelta(days=1))
    prices2._append(service2.fetch_prices())

    all_prices = pd.concat([prices, prices2], axis=1)
    if plot:
        import matplotlib.pyplot as plt
        import matplotlib.lines as lines
        ax = all_prices.plot(drawstyle="steps-post", linewidth=2)

        now = datetime.now(SpotpriceRequest.TZ)
        now_line = lines.Line2D([now,now], [0,300], linewidth=1)
        ax.add_line(now_line)

        plt.grid(True)
        plt.show()
    print(all_prices)


if __name__ == '__main__':
    import sys
    from time import sleep
    try:
        loop = sys.argv[1] == 'daemon'
    except:
        loop = False
        pass

    if loop:
        while True:
            sleep(10)
            main()
            sleep(3600*1)
    else:
        main(False)
