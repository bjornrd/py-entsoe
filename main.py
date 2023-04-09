import sys
from entsoe import core

if __name__ == '__main__':
    pricedata = core.getPriceData(core.Zone.NO4, currency=core.Currencies.NOK)

    if pricedata is not None:
        print(pricedata.price)
        print(pricedata.resolution)
        print(pricedata.description)


    sys.exit()

    