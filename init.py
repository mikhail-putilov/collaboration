# coding=utf-8
__author__ = 'snowy'

import logging
import sublime
import sublime_plugin
from collections import namedtuple
# import other
from twisted.python import log

from reactor import reactor


registry = {}
''':type registry: dict which maps "view_id" → (view's application, view's client_connection_string)'''

RegistryEntry = namedtuple('RegistryEntry', ['application', 'connection_string'])


class ViewIsNotInitializedError(Exception):
    pass


class ClientConnectionStringIsNotInitializedError(Exception):
    pass


# noinspection PyClassHasNoInit
class RunServerCommand(sublime_plugin.TextCommand):
    # noinspection PyUnusedLocal
    def run(self, edit):
        """
        Начальная инициализация серверной части.
        """
        from main import ViewAwareApplication

        app = ViewAwareApplication(reactor, self.view, name='Application{0}'.format(self.view.id()))
        log.msg('{0} is created'.format(app.name))

        # if not other.debugView:
        #     debugView = self.view

        def _cb(client_connection_string):
            registry[self.view.id()] = RegistryEntry(app, client_connection_string)
            log.msg('client_connection_string={0}'.format(client_connection_string), logLevel=logging.DEBUG)

        app.setUpServerFromStr('tcp:0').addCallback(_cb)


# noinspection PyClassHasNoInit
class RunClientCommand(sublime_plugin.TextCommand):
    # noinspection PyUnusedLocal
    def run(self, edit, connection_str=None):
        """
        Начальная инициализация серверной части.
        """
        if connection_str is None:
            raise ClientConnectionStringIsNotInitializedError()
        app = registry[self.view.id()].application
        app.connectAsClientFromStr(connection_str) \
            .addCallback(
            lambda ignore: log.msg('{0} has connected to {1}'.format(app.name, connection_str)))


class NumberOfWindowsIsNotSupportedError(Exception):
    pass


# noinspection PyClassHasNoInit
class ConnectTwoWindows(sublime_plugin.TextCommand):
    """
    Соединить два окна. Иницилизирует два пира, каждый из которых владеет одним окном ST.
    Текст в обоих окнах должен синхронизироваться
    """
    # noinspection PyUnusedLocal
    def run(self, edit):
        if len(sublime.windows()) != 2:
            raise NumberOfWindowsIsNotSupportedError('Create two windows and try again')

        windows = sublime.windows()[:2]
        for window in windows:
            window.active_view().run_command('run_server')
        self.connectToEachOther(windows[0], windows[1])

    @staticmethod
    def connectToEachOther(window1, window2):
        def _connect(_window1, _window2):
            entry = registry[_window1.active_view().id()]
            _window2.active_view().run_command('run_client', {'connection_str': entry.connection_string})

        _connect(window2, window1)
        _connect(window1, window2)


class ConnectTwoViewsCommand(sublime_plugin.TextCommand):
    """
    Соединить два view, если они единственны. см. ConnectTwoWindows
    """
    # noinspection PyUnusedLocal
    def run(self, edit):
        if len(sublime.windows()) != 1:
            raise NumberOfWindowsIsNotSupportedError('Create single window with exactly two views and try again')

        views = sublime.active_window().views()
        for view in views:
            view.run_command('run_server')
        self.connectToEachOther(views[0], views[1])

    @staticmethod
    def connectToEachOther(view1, view2):
        def _connect(_view1, _view2):
            entry = registry[_view1.id()]
            _view2.run_command('run_client', {'connection_str': entry.connection_string})

        _connect(view1, view2)
        _connect(view2, view1)