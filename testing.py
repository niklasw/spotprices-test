
import json
from datetime import datetime, timedelta
import pandas as pd


from utils.spot_price import entsoe_price_list as entsoe

conf = json.load(open('config/sensors.json'))

# entsoe_conf = conf.get('sources').get('entsoe').get('entsoe_price_list')
# E = entsoe(entsoe_conf)
# E.fetch_prices()
# E_prices = E.prices


from utils.price_providers import Elprisetjustnu as justnu

J = justnu(datetime.now())

prices = J.fetch_prices()

print("\nJustnu prices", type(prices))
for item in prices.items():
    print(item)

