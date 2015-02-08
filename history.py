# coding=utf-8
__author__ = 'snowy'


class HistoryLine(object):
    def __init__(self, history_owner):
        """
        Линия истории патчей текущего application.
        :param history_owner: main.Application
        """
        self.owner = history_owner

    def clean(self):
        pass