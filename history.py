# coding=utf-8
from collections import namedtuple

__author__ = 'snowy'

HistoryEntry = namedtuple('HistoryEntry', ['patch', 'timestamp', 'is_owner'])


class HistoryLine(object):
    def __init__(self, history_owner):
        """
        Линия истории патчей текущего application.
        :param history_owner: main.Application
        """
        self.owner = history_owner
        self.history = []

    def clean(self):
        del self.history
        self.history = []

    def commit(self, patch, timestamp, is_owner):
        assert not isinstance(patch, str)
        self.history.append(HistoryEntry(patch, timestamp, is_owner))

    def get_all_since(self, timestamp):
        return [entry for entry in self.history if entry.timestamp > timestamp]