__author__ = 'snowy'

import ntp

class Timestamp(object):
    def __init__(self, ctime):
        self._ctime = ctime

    @property
    def ctime(self):
        return self._ctime