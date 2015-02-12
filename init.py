# coding=utf-8
"""
Модуль начальной инициализации sublime плагина. Включает в себя в основном наследников sublime_plugin.TextCommand.
Логически является специфичной sublime оберткой над main модулем.
"""
import main

__author__ = 'snowy'

import logging
import sublime
import sublime_plugin
from collections import namedtuple
from twisted.python import log

from reactor import reactor


registry = {}
""":type registry: dict that maps "view_id" → "RegistryEntry" """

RegistryEntry = namedtuple('RegistryEntry', ['application', 'connection_string'])
running = False


def log_any_failure_and_errmsg_eb(failure):
    """
    В случае, если не получается apply patch, то выводим сообщение об ошибке, а не умираем тихо
    :param failure: twisted.python.Failure
    """
    failure.trap(Exception)
    sublime.error_message(failure.getErrorMessage() if failure else 'No failure message is found')
    assert Collaboration
    sublime.run_command('collaboration', {'start_or_stop': 'stop'})
    assert TerminateCollaborationCommand
    sublime.run_command('terminate_collaboration')


class ViewIsNotInitializedError(Exception):
    pass


class ClientConnectionStringIsNotInitializedError(Exception):
    pass


# noinspection PyClassHasNoInit
class RunServerCommand(sublime_plugin.TextCommand):
    # noinspection PyUnusedLocal
    def run(self, edit):
        """
        Начальная инициализация серверной части. Включая таймер.
        """
        from main import SublimeAwareApplication

        app = SublimeAwareApplication(reactor, self.view, name='Application{0}'.format(self.view.id()))
        log.msg('{0} is created'.format(app.name))

        def _cb(client_connection_string):
            registry[self.view.id()] = RegistryEntry(app, client_connection_string)
            log.msg('client_connection_string={0}'.format(client_connection_string), logLevel=logging.DEBUG)

        app.setUpServerFromStr('tcp:0').addCallback(_cb)


class InitArgumentIsNotInitializedError(Exception):
    pass


class RunClientCommand(sublime_plugin.TextCommand):
    # noinspection PyUnusedLocal
    def run(self, edit, connection_str=None, init=None):
        """
        Начальная инициализация серверной части.
        """
        if not connection_str:
            raise ClientConnectionStringIsNotInitializedError()
        if init is None:
            raise InitArgumentIsNotInitializedError()
        app = registry[self.view.id()].application
        d = app.connectAsClientFromStr(connection_str) \
            .addCallback(
            lambda ignore: log.msg('{0} has connected to {1}'.format(app.name, connection_str)))
        if init:
            global running
            running = True
            sublime.run_command('collaboration', {'start_or_stop': 'start'})


class NumberOfWindowsIsNotSupportedError(Exception):
    pass


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
        def _connect(_window1, _window2, isInited):
            entry = registry[_window1.active_view().id()]
            _window2.active_view().run_command('run_client',
                                               {'connection_str': entry.connection_string, 'init': isInited})

        _connect(window2, window1, False)
        _connect(window1, window2, True)


class ConnectTwoViewsCommand(sublime_plugin.TextCommand):
    """
    Соединить два view, если они единственны. см. ConnectTwoWindows
    """
    # noinspection PyUnusedLocal
    def run(self, edit):
        if len(sublime.windows()) != 1:
            raise NumberOfWindowsIsNotSupportedError('Create single window with exactly two views and try again')

        sublime.run_command('terminate_collaboration')

        views = sublime.active_window().views()
        for view in views:
            edit = view.begin_edit()
            try:
                view.erase(edit, sublime.Region(0, view.size()))
            finally:
                view.end_edit(edit)
            view.run_command('run_server')
        self.connectToEachOther(views[0], views[1])

    @staticmethod
    def connectToEachOther(view1, view2):
        def _connect(_view1, _view2, isInited):
            entry = registry[_view1.id()]
            _view2.run_command('run_client', {'connection_str': entry.connection_string, 'init': isInited})

        _connect(view1, view2, False)
        _connect(view2, view1, True)


class ConnectTwoViewsWithCoordinatorCommand(sublime_plugin.TextCommand):
    """
    Соединить два view, если они единственны. см. ConnectTwoWindows используя координирующий сервер
    """

    @staticmethod
    def pre_conditions_check():
        if len(sublime.windows()) != 1:
            raise NumberOfWindowsIsNotSupportedError('Create single window with exactly two views and try again')

    @staticmethod
    def erase_view(view):
        edit = view.begin_edit()
        try:
            view.erase(edit, sublime.Region(0, view.size()))
        finally:
            view.end_edit(edit)

    def run(self, edit):
        self.pre_conditions_check()

        sublime.run_command('terminate_collaboration')

        views = sublime.active_window().views()
        for view in views:
            self.erase_view(view)
            view.run_command('run_server')

        coordinator_created_cb = lambda ignore: self.connect_to_each_other(views[0], views[1])

        def _eb(failure):
            sublime.error_message(failure.getErrorMessage())
            log.err(failure)

        self.run_coordinator_server().addCallback(coordinator_created_cb).addErrback(_eb)


    @staticmethod
    def connect_to_each_other(view1, view2):
        def _connect_to_coordinator(_view, isInited):
            entry = registry['coordinator']
            _view.run_command('run_client', {'connection_str': entry.connection_string, 'init': isInited})

        _connect_to_coordinator(view1, False)
        _connect_to_coordinator(view2, True)

    @staticmethod
    def run_coordinator_server():
        from core.core import CoordinatorApplication

        app = CoordinatorApplication(reactor)
        log.msg('{0} is created'.format(app.name))

        def _cb(client_connection_string):
            registry['coordinator'] = RegistryEntry(app, client_connection_string)

        return app.setUpServerFromStr('tcp:0').addCallback(_cb)


class StartOrStopFlagMustBeSetException(Exception):
    pass


class StartOrStopArgumentIllegalValues(Exception):
    pass


class ViewsDivergeException(Exception):
    pass


class Collaboration(sublime_plugin.ApplicationCommand):
    def __init__(self):
        from twisted.internet import task

        self.run_every_second_task = task.LoopingCall(main.run_every_second)

    def run(self, start_or_stop=None):
        if start_or_stop is None:
            raise StartOrStopFlagMustBeSetException('Available values are "start" or "stop".')
        if start_or_stop == 'start':
            if not self.run_every_second_task.running:
                self.run_every_second_task.start(1.0)
        elif start_or_stop == 'stop':
            if self.run_every_second_task.running:
                self.run_every_second_task.stop()
                global running
                running = False
        else:
            raise StartOrStopArgumentIllegalValues('Available values are "start" or "stop".')


class TerminateCollaborationCommand(sublime_plugin.ApplicationCommand):
    @staticmethod
    def run():
        global registry
        del registry
        registry = {}
