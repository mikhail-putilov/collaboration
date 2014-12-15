# coding=utf-8
__author__ = 'snowy'


class Message(object):
    """Сообщение, передаваемое между участниками сети"""

    def __init__(self, sender, patch, timestamp):
        """
        :type timestamp: Timestamp Время отправления сообщения
        :type patch: Patch Сделанные изменения
        :type sender: Sender Отправитель
        """
        self._timestamp = timestamp
        self._patch = patch
        self._sender = sender

    @property
    def patch(self):
        return self._patch

    @property
    def sender(self):
        return self._sender

    @property
    def timestamp(self):
        return self._timestamp