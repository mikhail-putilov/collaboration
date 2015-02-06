# coding=utf-8
from other import supervisor_for_2column_layout

__author__ = 'snowy'

import logging
import sublime
import sublime_plugin
from collections import namedtuple
from twisted.python import log

from reactor import reactor


registry = {}
''':type registry: dict which maps "view_id" → (view's application, view's client_connection_string)'''

RegistryEntry = namedtuple('RegistryEntry', ['application', 'connection_string'])
running = False


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

        def _cb(client_connection_string):
            registry[self.view.id()] = RegistryEntry(app, client_connection_string)
            log.msg('client_connection_string={0}'.format(client_connection_string), logLevel=logging.DEBUG)

        app.setUpServerFromStr('tcp:0').addCallback(_cb)


class InitArgumentIsNotInitializedError(Exception):
    pass


# noinspection PyClassHasNoInit
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
            sublime.run_command('start_collaboration_listening')



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


def run_every_second():
    """Функция, которая запускает синхронизацию между view"""
    for view_id in registry:
        app = registry[view_id].application
        allTextRegion = sublime.Region(0, app.view.size())
        allText = app.view.substr(allTextRegion)
        app.algorithm.local_onTextChanged(allText) \
            .addCallback(supervisor_for_2column_layout) \
            .addErrback(log_any_failure_and_errmsg_eb)


def log_any_failure_and_errmsg_eb(failure):
    """
    В случае, если не получается apply patch, то выводим сообщение об ошибке, а не умираем тихо
    :param failure: twisted.python.Failure
    """
    failure.trap(Exception)
    log.err(failure)
    sublime.error_message(str(failure))
    sublime.run_command('stop_collaboration_listening')
    sublime.run_command('terminate_collaboration')


# noinspection PyMethodMayBeStatic
class TerminateCollaborationCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        global registry
        del registry
        registry = {}


from twisted.internet import task

run_every_second_task = task.LoopingCall(run_every_second)


# noinspection PyMethodMayBeStatic
class StartCollaborationListeningCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        if not run_every_second_task.running:
            run_every_second_task.start(1.0)


# noinspection PyMethodMayBeStatic
class StopCollaborationListeningCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        if run_every_second_task.running:
            run_every_second_task.stop()