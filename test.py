#!/usr/bin/env python3

from utils.spot_price import PriceList, Entsoe
from datetime import datetime

if __name__ == '__main__':
    price_list = PriceList('prices.json', Entsoe())
    price_list.update()

    print(price_list.current_price())
    print(price_list.current_ranking())
