from collector import DataCollector
from fxdayu_data.data.base import MongoHandler
from datetime import datetime
import pandas as pd
import json
import oandapy


def frame_shape(function):
    def frame_wrap(*args, **kwargs):
        if kwargs.pop('frame', True):
            return pd.DataFrame(function(*args, **kwargs))
        else:
            return function(*args, **kwargs)

    return frame_wrap


def time_shape(transfer=datetime.fromtimestamp, source='timestamp', *a, **k):
    def time_wrapper(function):
        def wrapper(*args, **kwargs):
            data = function(*args, **kwargs)
            for doc in data:
                doc['datetime'] = transfer(doc[source], *a, **k)
            return data
        return wrapper
    return time_wrapper


class OandaAPI(oandapy.API):

    @frame_shape
    @time_shape(datetime.strptime, 'time', '%Y-%m-%dT%H:%M:%S.%fZ')
    def get_history(self, instrument, **params):
        if isinstance(params.get('start', None), datetime):
            params['start'] = params['start'].strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        if isinstance(params.get('end', None), datetime):
            params['end'] = params['end'].strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        params.setdefault('candleFormat', 'midpoint')
        params.setdefault('dailyAlignment', 0)
        params.setdefault('alignmentTimezone', 'UTC')

        if params.pop('all', False):
            try:
                return super(oandapy.API, self).get_history(instrument=instrument, **params)['candles']
            except oandapy.OandaError as oe:
                if '5000' in str(oe):
                    if 'start' in params:
                        return self._get_history(instrument, **params)
                    else:
                        raise ValueError('Requires start if count > 5000')

        else:
            return super(oandapy.API, self).get_history(instrument=instrument, **params)['candles']

    def _get_history(self, instrument, **params):
        if 'count' in params:
            target = params['count']
            params['count'] = 5000
            data = super(oandapy.API, self).get_history(instrument=instrument, **params)['candles']
            count = target - len(data)
            params['includeFirst'] = 'false'
            while count > 5000:
                params['start'] = data[-1]['time']
                data.extend(super(oandapy.API, self).get_history(instrument=instrument, **params)['candles'])
                count = target - len(data)

            if count:
                params['count'] = count
                params['start'] = data[-1]['time']
                data.extend(super(oandapy.API, self).get_history(instrument=instrument, **params)['candles'])

            return data

        end = params.pop('end', None)
        params['count'] = 5000

        data = super(oandapy.API, self).get_history(instrument=instrument, **params)['candles']
        try:
            params['start'] = data[-1]['time']
            params['includeFirst'] = 'false'
            params['end'] = end
            next_data = super(oandapy.API, self).get_history(instrument=instrument, **params)['candles']
        except oandapy.OandaError as oe:
            if '5000' in str(oe):
                next_data = self._get_history(instrument, **params)
            else:
                return data
        except IndexError:
            return data

        data.extend(next_data)
        return data

    @frame_shape
    @time_shape()
    def get_eco_calendar(self, instrument, period=31536000):
        return super(OandaAPI, self).get_eco_calendar(instrument=instrument, period=period)

    @frame_shape
    @time_shape(source='date')
    def get_commitments_of_traders(self, instrument, period=31536000):
        return super(OandaAPI, self).get_commitments_of_traders(instrument=instrument, period=period)[instrument]

    @frame_shape
    @time_shape()
    def get_historical_position_ratios(self, instrument, period=31536000):
        data = super(OandaAPI, self).get_historical_position_ratios(instrument=instrument, period=period)
        columns = ['timestamp', 'long_position_ratio', 'exchange_rate']

        return [dict(list(map(lambda key, value: (key, value), columns, doc)))
                for doc in data['data'][instrument]['data']]


class OandaData(DataCollector):

    API_MAP = {
        'HPR': 'get_historical_position_ratios',
        'CLD': 'get_eco_calendar',
        'COT': 'get_commitments_of_traders'
    }

    MAIN_CURRENCY = [
        'EUR_USD', 'AUD_USD', 'NZD_USD', 'GBP_USD', 'USD_CAD', 'USD_JPY'
    ]

    default_period = [
        'M15', 'M30', 'H1', 'H4', 'D', 'M'
    ]

    def __init__(self, oanda_info, host='localhost', port=27017, db='Oanda', user={}, **kwargs):
        """

        :param oanda_info: dict, oanda account info {'environment': 'practice', 'access_token': your access_token}
        :return:
        """

        super(OandaData, self).__init__(MongoHandler(host, port, user, db, **kwargs))

        if isinstance(oanda_info, str):
            with open(oanda_info) as info:
                oanda_info = json.load(info)
                info.close()

        self.api = OandaAPI(environment=oanda_info.get('environment', 'practice'),
                            access_token=oanda_info.get('access_token', None))

    def save_history(self, instrument, **kwargs):
        kwargs['frame'] = False
        try:
            result = self.api.get_history(instrument, **kwargs)
        except oandapy.OandaError as oe:
            print (oe.message)
            if oe.error_response['code'] == 36:
                return self.save_div(instrument, **kwargs)
            else:
                raise oe

        self.client.inplace(
            result,
            '.'.join((instrument, kwargs.get('granularity', 'S5'))),
        )

        return {'start': result[0], 'end': result[-1]}

    def save_div(self, instrument, **kwargs):
        if 'start' in kwargs:
            end = kwargs.pop('end', None)
            kwargs['count'] = 5000
            result = self.save_history(instrument, **kwargs)

            kwargs.pop('count')
            if end:
                kwargs['end'] = end
            kwargs['start'] = result['end']['time']
            kwargs['includeFirst'] = 'false'
            next_result = self.save_history(instrument, **kwargs)
            result['end'] = next_result['end']
            return result
        else:
            raise ValueError('In save data mode, start is required')

    def save_many(self, instruments, granularity, start, end=None, t=5):
        if isinstance(instruments, list):
            if isinstance(granularity, list):
                self._save_many(
                    start, end, t,
                    [(i, g) for i in instruments for g in granularity]
                )

            else:
                self._save_many(
                    start, end, t,
                    [(i, granularity) for i in instruments]
                )

        else:
            if isinstance(granularity, list):
                self._save_many(
                    start, end, t,
                    [(instruments, g) for g in granularity]
                )

            else:
                self.save_history(instruments, granularity=granularity, start=start, end=end)

    def _save_many(self, start, end, t, i_g):
        for i, g in i_g:
            self.queue.put({
                'instrument': i,
                'granularity': g,
                'start': start,
                'end': end
            })

        self.start(self.save_history, t)
        self.stop()
        self.join()

    def save_main(self, start=datetime(2010, 1, 1), end=datetime.now()):
        self.save_many(self.MAIN_CURRENCY, self.default_period, start, end)

    def update(self, col_name):
        doc = self.client.db[col_name].find_one(sort=[('datetime', -1)], projection=['time'])
        if doc is None:
            raise ValueError('Unable to find the last record or collection: %s, '
                             'please check your DataBase' % col_name)

        i, g = col_name.split('.')
        if g in self.API_MAP:
            return self.save(g, col_name, instrument=i)
        else:
            return self.save_history(i, granularity=g, start=doc['time'], includeFirst=False)

    def update_candle(self, i, g, **kwargs):
        return self.save_history(i, granularity=g, **kwargs)

    def update_many(self, col_names=[], t=5):
        if len(col_names) == 0:
            col_names = self.client.db.collection_names()

        for col_name in col_names:
            self.queue.put({'col_name': col_name})

        self.start(self.update, t)
        self.stop()
        self.join()

    def save(self, api, collection=None, db=None, **kwargs):
        kwargs['frame'] = False
        if collection is None:
            collection = kwargs['instrument'] + '.' + api
        self.client.inplace(getattr(self.api, self.API_MAP[api])(**kwargs), collection, db)
