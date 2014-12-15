__author__ = 'snowy'


class Timestamp(object):
    def __init__(self, ctime):
        self._ctime = ctime

    @property
    def ctime(self):
        return self._ctime