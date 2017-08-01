try:
    from fxdayu_data.handler.mongo_handler import MongoHandler
    import fxdayu_data.handler.mongo_handler as mongo
except ImportError:
    pass

try:
    from fxdayu_data.handler.redis_handler import RedisHandler
except ImportError:
    pass

try:
    from fxdayu_data.collector.oanda_api import OandaAPI
except ImportError:
    pass


from fxdayu_data.collector import sina_tick
from fxdayu_data.collector.quests import QuestHandler, Quest


__all__ = ['MongoHandler', "mongo"
           "RedisHandler", "OandaAPI", "sina_tick", "Quest", "QuestHandler"]