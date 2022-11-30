from matplotlib import pyplot as plt
from datetime import timedelta


def plot(prices, slots):
    _, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
    x = prices.index
    slots.plot(ax=ax1, kind='line', color='red')
    prices.plot(ax=ax2, kind='line', color='green', drawstyle='steps-post')
    ax1.set_xlim(x[0], x[-1]+timedelta(hours=1))
    ax1.set_title('on/off signal, 6 hours daily demand')
    ax2.set_xlim(x[0], x[-1]+timedelta(hours=1))
    ax2.set_title('spot price')
    ax1.grid('on')
    ax2.grid('on')
    plt.show()
