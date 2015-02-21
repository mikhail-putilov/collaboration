import logging

__author__ = 'snowy'


class ApplicationSpecificAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '[%s] %s' % (self.extra['name'], msg), kwargs