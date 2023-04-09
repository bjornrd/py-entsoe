
from entsoe import keys
import sys
from datetime import date, datetime, timedelta
from enum import Enum
import requests
import xml.sax
import json


# Price-Zone definitions
# ----------------------------------------------------------------
class Zone(Enum):
    NO1: str = "10YNO-1--------2"
    NO2: str = "10YNO-2--------T"
    NO3: str = "10YNO-3--------J"
    NO4: str = "10YNO-4--------9"
    NO5: str = "10Y1001A1001A48H"

# Conversion Currencies
# ----------------------------------------------------------------
class Currencies(Enum):
    NOK: str = "NOK"
    EUR: str = "EUR"
    USD: str = "USD"
    GBP: str = "GBP"


# Retrieve entso-e price data
# ----------------------------------------------------------------
def getPriceData(zone: Zone, priceDate: date = date.today(), currency: Currencies = Currencies.EUR, *args, **kwargs):
    Handler = PriceDataHandler()
    if len(keys.entsoeapi_key) == 0:
        print("No Valid Entso-E-Key set so not trying to get data: Please set entsoeapi_key in keys.py", file=sys.stderr)
        return None # We don't have a key, so we won't get any data from entso-e
    
    retstring = requests.get('https://web-api.tp.entsoe.eu/api?documentType=A44' + 
                             '&In_Domain=' + zone.value +
                             '&out_Domain=' + zone.value + 
                             '&periodStart=' + priceDate.strftime("%Y%m%d")  + '0100' + 
                             '&periodEnd=' + priceDate.strftime("%Y%m%d") + '2200' + 
                             '&securityToken=' + keys.entsoeapi_key).content
    
    xml.sax.parseString(retstring, Handler)

    starttime = datetime.strptime(Handler.start, "%Y-%m-%dT%H:%MZ")
    endtime = datetime.strptime(Handler.end, "%Y-%m-%dT%H:%MZ")
    priceDataObj = PriceData(Handler.price, Handler.position, priceDate, resolution=Handler.resolution, starttime=starttime, endtime=endtime)


    # Handle currency
    if priceDataObj.currency != currency:
        currencyConverterObj = Currency()
        currencyConverterObj.convert(priceDataObj.currency, currency)

        if len(currencyConverterObj.errorMessage) != 0:
            print(currencyConverterObj.errorMessage, file=sys.stderr)
        else:        
            priceDataObj.currency = currency

            pricetmp = priceDataObj.price.copy()
            priceDataObj.price.clear()
            for price in pricetmp:        
                priceDataObj.price.append(price*currencyConverterObj.conversionFactor)      

            priceDataObj.description = priceDataObj.currency.value + "/MWh"

    return priceDataObj




# Price Data Class
# ----------------------------------------------------------------
class PriceData:
    def __init__(self, price: list[float] = list(), idx: list[int] = list(), priceDate: date = None, currency: Currencies = Currencies.EUR, resolution: str=None, starttime: datetime = None, endtime: datetime = None, *args, **kwargs):
        self.price: list[float] = price
        self.idx: list[int] = idx
        self.resolution: str = resolution
        self.priceDate: date = priceDate
        self.currency: Currencies = currency
        self.description: str = currency.value + "/MWh"     
        self.starttime: datetime = starttime
        self.endtime: datetime = endtime
        self.timearray = self.__createTimeArray(self.starttime, self.endtime)


    # Helper method to create time array from start- and end time in entsoe response
    def __createTimeArray(self, time1: datetime, time2: datetime) -> list[datetime]:
        timediff = time2 - time1
        hours = int(timediff.days*24 + timediff.seconds/3600)
        date_list = [time1 + timedelta(hours=x+2) for x in range(hours)] # +2 as time from entsoe is GMT (Zulu)

        return date_list



# XML Parser Handler
# ----------------------------------------------------------------
class PriceDataHandler(xml.sax.ContentHandler):
    class PriceTags(Enum):
        price: str = "price.amount"
        position: str = "position"
        resolution: str = "resolution"
        start: str = "start"
        end: str = "end"

    def __init__(self):
        self.CurrentData = ""
        self.resolution: str = ""
        self.position: list[int] = list()
        self.price: list[float] = list()

    # Call when an element starts
    def startElement(self, tag, attributes):
        self.CurrentData = tag

    # Call when an elements ends
    def endElement(self, tag):
        self.CurrentData = ""

    # Call when a character is read
    def characters(self, content):
        if self.CurrentData == PriceDataHandler.PriceTags.resolution.value:
            self.resolution = content
        elif self.CurrentData == PriceDataHandler.PriceTags.position.value:
            self.position.append(int(content))
        elif self.CurrentData == PriceDataHandler.PriceTags.price.value:
            self.price.append(float(content))
        elif self.CurrentData == PriceDataHandler.PriceTags.start.value:
            self.start = content
        elif self.CurrentData == PriceDataHandler.PriceTags.end.value:
            self.end = content


# Currency Conversion Class
# ----------------------------------------------------------------
class Currency:
    def __init__(self):
        self.date: date
        self.fromCurrency: Currencies
        self.toCurrency: Currencies
        self.conversionFactor: float
        self.errorMessage: str = ""

    def convert(self, fromCurrency: Currencies, toCurrency: Currencies, conversionDate: str = date.today().strftime("%Y-%m-%d")):

        if len(keys.freecurrencyapi_key) == 0:
            self.conversionFactor = 1
            self.errorMessage = "No Valid FreeCurrencyAPI-Key set so not doing currency conversion: Please set freecurrencyapi_key in keys.py"
            return # No valid key is set so just return as we won't get any data from freecurrencyapi

        currencyResponse = requests.get('https://api.currencyapi.com/v3/latest?apikey=' + keys.freecurrencyapi_key + 
                                        '&base_currency=' + fromCurrency.value + 
                                        '&date=' + conversionDate).text
        
        currency_parsed = json.loads(currencyResponse)
        self.conversionFactor = float(currency_parsed["data"][toCurrency.value]["value"])
        self.fromCurrency = fromCurrency
        self.toCurrency = toCurrency