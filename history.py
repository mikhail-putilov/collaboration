# coding=utf-8
from collections import namedtuple

__author__ = 'snowy'

HistoryEntry = namedtuple('HistoryEntry', ['patch', 'timestamp', 'is_owner'])


class HistoryLine(object):
    def __init__(self, history_owner):
        """
        Линия истории патчей текущего application.
        :param history_owner: core.core.Application
        """
        self.owner = history_owner
        # История, которая держит патчи, обратные к тем, что лежат в self.history
        # необходимо для верного rollback патчей
        self.rollback_history = []
        # История примененных патчей
        self.history = []

    def clean(self):
        del self.history
        self.history = []

    def commit(self, patch, timestamp, is_owner):
        self._commit(HistoryEntry(patch, timestamp, is_owner), self.history)

    @staticmethod
    def _commit(entry, where):
        assert isinstance(entry, HistoryEntry)
        where.append(entry)

    def commit_with_rollback(self, forwards, backwards):
        """
        Комит изменений с rollback патчем
        :param forwards: HistoryEntry стандартный патч, применение которого ведет вперед по истории
        :param backwards: HistoryEntry патч, являющийся обратным к forwards
        """
        self._commit(forwards, self.history)
        self._commit(backwards, self.rollback_history)

    def get_all_since(self, timestamp):
        return [entry for entry in self.history if entry.timestamp > timestamp]
