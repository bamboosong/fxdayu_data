from fxdayu_data.data import MongoHandler
from datetime import datetime
import pandas as pd


OANDA_MAPPER = {'open': 'openMid',
                'high': 'highMid',
                'low': 'lowMid',
                'close': 'closeMid'}


class MarketData(object):

    def __init__(self, client=None, host='localhost', port=27017, users={}, db=None, **kwargs):
        self.client = client if client else MongoHandler(host, port, users, db, **kwargs)
        self.read = self.client.read
        self.write = self.client.write
        self.inplace = self.client.inplace
        self.initialized = False
        self.frequency = None
        self._panels = {}
        self.mapper = {}

        self._db = self.client.db
        self._time = datetime.now()

    def init(self, symbols, frequency, start=None, end=None, db=None):
        panel = self._read_db(symbols, frequency, ['open', 'high', 'low', 'close', 'volume'], start, end, None, db)
        self._panels[frequency] = panel
        self.frequency = frequency
        self._db = db if db else self.client.db
        self.initialized = True

    def current(self, symbol=None):
        panel = self._panels[self.frequency]

        try:
            if symbol is None:
                symbol = list(panel.items)
                if len(symbol) == 1:
                    symbol = symbol[0]
            if not isinstance(symbol, (tuple, list)):
                if symbol not in panel.items:
                    raise KeyError()
                else:
                    index = self.search_axis(panel.major_axis, self._time)
                    return panel[symbol].iloc[index]
            if isinstance(symbol, list):
                for s in symbol:
                    if s not in panel.items:
                        raise KeyError()

            index = self.search_axis(panel.major_axis, self._time)
            return panel[symbol].iloc[:, index]
        except KeyError:
            return self._read_db(symbol, self.frequency, None, None, self._time, 1, self._db)[symbol].iloc[:, -1]

    def history(self, symbol=None, frequency=None, fields=None, start=None, end=None, length=None, db=None):
        if frequency is None:
            frequency = self.frequency
        try:
            if symbol is None:
                symbol = list(self._panels[frequency].items)
            result = self._read_panel(symbol, frequency, fields, start, end, length)
            if self.match(result, symbol, length):
                return result
            else:
                raise KeyError()
        except KeyError:
            if symbol is None:
                symbol = list(self._panels[self.frequency].items())
            return self._read_db(symbol, frequency, fields, start, end, length, db if db else self._db)

    def _read_panel(self, symbol, frequency, fields, start, end, length):
        panel = self._panels[frequency]
        major_slice = self.major_slice(panel.major_axis, self._time, start, end, length)
        result = self._find(panel, symbol, major_slice, fields if fields else slice(None))
        return result

    def _read_db(self, symbols, frequency, fields, start, end, length, db):
        symbols = [symbols] if isinstance(symbols, str) else symbols
        if fields is None:
            fields = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        elif isinstance(fields, str):
            fields = ['datetime', fields]
        elif 'datetime' not in fields:
            fields.append('datetime')

        mapper = self.mapper.get(db, None)
        result = {}
        if mapper is None:
            for symbol in symbols:
                result[symbol] = self.client.read(
                    '.'.join((symbol, frequency)),
                    db, 'datetime', start, end, length,
                    projection=fields
                )
        else:
            fields = [mapper.get(key, key) for key in fields]
            trans_map = {item[1]: item[0] for item in mapper.items()}
            for symbol in symbols:
                result[symbol] = self.client.read(
                    '.'.join((symbol, frequency)),
                    db, 'datetime', start, end, length,
                    projection=fields
                ).rename_axis(trans_map, axis=1)

        return pd.Panel(result)

    @staticmethod
    def match(result, items, length):
        if isinstance(result, pd.DataFrame):
            if len(result) == length:
                return True
            else:
                return False
        elif isinstance(result, pd.Panel):
            if (len(items) == len(result.items)) and (len(result.major_axis) == length):
                return True
            else:
                return False
        else:
            return False

    @staticmethod
    def _find(panel, item, major, minor):
        if item is not None:
            if isinstance(item, str):
                frame = panel[item]
                return frame[minor].iloc[major]
            else:
                panel = panel[item]
                return panel[:, major, minor]
        else:
            if len(panel.items) == 1:
                return panel[panel.items[0]][minor].iloc[major]
            else:
                return panel[:, major, minor]

    @staticmethod
    def search_axis(axis, time):
        index = axis.searchsorted(time)
        if index < len(axis):
            if axis[index] <= time:
                return index
            else:
                return index - 1
        else:
            return len(axis) - 1

    def major_slice(self, axis, now, start, end, length):
        last = self.search_axis(axis, now)

        if end:
            end = self.search_axis(axis, end)
            if end > last:
                end = last
        else:
            end = last

        if start:
            start = axis.searchsorted(pd.to_datetime(start))
            if length:
                if start + length <= end+1:
                    return slice(start, start+length)
                else:
                    return slice(start, end+1)
            else:
                return slice(start, end+1)
        elif length:
            end += 1
            if end < length:
                raise IndexError()
            return slice(end-length, end)
        else:
            return slice(0, end+1)


if __name__ == '__main__':
    from datetime import datetime
    cd = MarketData()
    db = 'HS'
    codes = cd.client.table_names(db)
    cd.mapper['Oanda'] = OANDA_MAPPER
    cd.init(['EUR_USD', 'GBP_USD'], 'D', datetime(2016, 1, 1), db='Oanda')
    print cd.current('EUR_USD')