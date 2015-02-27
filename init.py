# coding=utf-8
"""
Модуль начальной инициализации sublime плагина. Включает в себя в основном наследников sublime_plugin.TextCommand.
Логически является специфичной sublime оберткой над main модулем.
"""
import main
from misc import erase_view

__author__ = 'snowy'

import logging
import sublime
import sublime_plugin
from collections import namedtuple
import twisted.internet.defer as defer

from reactor import reactor

logger = logging.getLogger(__name__)

registry = {}
""":type registry: dict that maps "view_id" → "RegistryEntry" """

RegistryEntry = namedtuple('RegistryEntry', ['application', 'connection_string'])


def log_any_failure_and_errmsg_eb(failure):
    failure.trap(Exception)
    sublime.error_message(failure.getErrorMessage() if failure else 'No failure message is found')
    terminate_collaboration()


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
        logger.debug('%s is created', app.name)

        def _cb(client_connection_string):
            registry[self.view.id()] = RegistryEntry(app, client_connection_string)
            logger.debug('client_connection_string=%s', client_connection_string)

        app.setUpServerFromStr('tcp:0').addCallback(_cb)


def run_client(view, connection_str):
    """
    Начальная инициализация серверной части.
    """
    app = registry[view.id()].application

    def _cb(_):
        logger.debug('%s has connected to %s', app.name, connection_str)
        return _

    return app.connectAsClientFromStr(connection_str).addCallback(_cb)


class NumberOfWindowsIsNotSupportedError(Exception):
    pass


class NumberOfViewsIsNotSupportedError(Exception):
    pass


class ConnectTwoViewsWithCoordinatorCommand(sublime_plugin.TextCommand):
    """
    Соединить два view, если они единственны. см. ConnectTwoWindows используя координирующий сервер
    """

    @staticmethod
    def pre_conditions_check():
        if len(sublime.windows()) != 1:
            raise NumberOfWindowsIsNotSupportedError('Create single window with exactly two views and try again')
        if len(sublime.active_window().views()) != 2:
            raise NumberOfViewsIsNotSupportedError('Create single window with exactly two views and try again')

    def run(self, edit):
        self.pre_conditions_check()

        terminate_collaboration()

        views = sublime.active_window().views()
        for view in views:
            erase_view(view)
            view.run_command('run_server')

        def _cb(_):
            return connect_to_each_other(views[0], views[1])

        def _connected_cb(_):
            sublime.run_command('collaboration', {'listening': 'start'})
            logger.info('{0} collaboration inited {0}'.format('---*---'))

        run_coordinator_server().addCallback(_cb).addCallback(_connected_cb)


def run_coordinator_server():
    from core.core import CoordinatorApplication

    app = CoordinatorApplication(reactor)
    logger.debug('%s is created', app.name)

    def _cb(client_connection_string):
        registry['coordinator'] = RegistryEntry(app, client_connection_string)

    return app.setUpServerFromStr('tcp:0').addCallback(_cb)


def connect_to_each_other(view1, view2):
    d1 = run_client(view1, registry['coordinator'].connection_string)
    d2 = run_client(view2, registry['coordinator'].connection_string)
    return defer.gatherResults([d1, d2])


class ListeningArgumentMustBeSetException(Exception):
    pass


class ViewsDivergeException(Exception):
    pass


class Collaboration(sublime_plugin.ApplicationCommand):
    def __init__(self):
        from twisted.internet import task

        self.run_every_second_task = task.LoopingCall(main.run_every_second)

    def run(self, listening=None):
        if listening == 'start':
            if not self.run_every_second_task.running:
                self.run_every_second_task.start(1.0)
        elif listening == 'stop':
            if self.run_every_second_task.running:
                self.run_every_second_task.stop()
        else:
            raise TypeError('"listening" argument legal values are "start" or "stop".')


def terminate_collaboration():
    assert Collaboration
    sublime.run_command('collaboration', {'listening': 'stop'})
    global registry
    registry = {}