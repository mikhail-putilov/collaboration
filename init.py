# coding=utf-8
"""
Модуль начальной инициализации sublime плагина. Включает в себя в основном наследников sublime_plugin.TextCommand.
Логически является специфичной sublime оберткой над main модулем.
"""
from twisted.internet import task, threads
import main
from misc import erase_view
import misc

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


class ViewIsNotInitializedError(Exception):
    pass


class ClientConnectionStringIsNotInitializedError(Exception):
    pass


def run_server(view):
    from main import SublimeAwareApplication

    app = SublimeAwareApplication(reactor, view, name='Application{0}'.format(view.id()))
    logger.debug('%s is created', app.name)

    def _cb(client_connection_string):
        registry[view.id()] = RegistryEntry(app, client_connection_string)
        logger.debug('client_connection_string=%s', client_connection_string)

    return app.setUpServerFromStr('tcp:0').addCallback(_cb)


def run_client(view, connection_str):
    assert view.id() in registry, "view's id must be in registry"
    app = registry[view.id()].application

    # noinspection PyUnusedLocal
    def _cb(client_proto):
        logger.debug('%s has connected to %s', app.name, connection_str)

    return app.connectAsClientFromStr(connection_str).addCallback(_cb)


class NumberOfWindowsIsNotSupportedError(Exception):
    pass


class NumberOfViewsIsNotSupportedError(Exception):
    pass


class ConnectTwoViewsWithCoordinatorCommand(sublime_plugin.WindowCommand):
    """
    Соединить два view, если они единственны. см. ConnectTwoWindows используя координирующий сервер
    """

    def pre_conditions_check(self):
        if len(self.window.views()) != 2:
            raise NumberOfViewsIsNotSupportedError('Create window with exactly two views and try again')

    def run(self):
        self.pre_conditions_check()

        views = self.window.views()
        d_list = []
        for view in views:
            terminate_collaboration(view.id())
            erase_view(view)
            d_list.append(run_server(view))

        def _cb(_):
            return connect_to_each_other(views[0], views[1])

        def _connected_cb(_):
            sublime.run_command('collaboration', {'listening': 'start', 'view_id': views[0].id()})
            sublime.run_command('collaboration', {'listening': 'start', 'view_id': views[1].id()})
            logger.info('{0} collaboration inited {0}'.format('---*---'))

        d_list.append(run_coordinator_server())
        defer.DeferredList(d_list).addCallback(_cb).addCallback(_connected_cb)


class AcceptConnections(sublime_plugin.WindowCommand):
    """
    Слушать первичные подключения
    """

    def run(self):
        view = self.window.active_view()
        terminate_collaboration(view.id())
        erase_view(view)

        d_list = [run_server(view), run_coordinator_server()]

        def _servers_up(_):
            run_client(view, registry['coordinator'].connection_string)
            logger.info(registry['coordinator'].connection_string)
            sublime.run_command('collaboration', {'listening': 'start', 'view_id': view.id()})

        defer.DeferredList(d_list).addCallback(_servers_up)


class ListOfLocalCoordinators(sublime_plugin.WindowCommand):
    """
    Подключиться к сессии используя список локальных координаторов
    """

    def run(self):
        import libs.beacon as beacon

        l = task.LoopingCall(misc.loading)
        l.start(0.1)
        d = threads.deferToThread(beacon.find_all_servers, 12000, b"collaboration-sublime-text")

        def _found(res_list):
            l.stop()
            sublime.status_message("A list of available coordinators is retrieved" if len(
                res_list) > 0 else "No coordinators answer your request. Try to connect with your bare hands.")
            items = [str(item) for item in res_list]

            def on_done(index):
                if index != -1:
                    on_get_connection_str(self.window, "tcp:host={0}:port=13256".format(items[index]))

            self.window.show_quick_panel(items, on_done)

        d.addCallback(_found)


class ConnectToCoordinator(sublime_plugin.WindowCommand):
    """
    Подключиться к сессии используя точный connection string
    """

    def run(self):
        on_done = lambda conn_str: on_get_connection_str(self.window, conn_str)
        self.window.show_input_panel("connection string:", "tcp:host={}:port=13256", on_done, None, None)


def on_get_connection_str(window, conn_str):
    if 'coordinator' not in registry:
        registry['coordinator'] = RegistryEntry(application=None, connection_string=conn_str)
    view = window.active_view()
    try:
        d = run_server(view).addCallback(lambda _: run_client(view, conn_str))
        d.addCallback(lambda _: sublime.run_command('collaboration', {'listening': 'start', 'view_id': view.id()}))
    except BaseException as e:
        logger.error("Couldn't connect to %s. An error occurred: %s", conn_str, e.message)
        if 'coordinator' in registry:
            del registry['coordinator']


def run_coordinator_server():
    from core.core import CoordinatorApplication

    app = CoordinatorApplication(reactor)
    logger.debug('%s is created', app.name)

    def _cb(client_connection_string):
        registry['coordinator'] = RegistryEntry(app, client_connection_string)

    return app.setUpServerFromStr('tcp:13256').addCallback(_cb)


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
        self.view_id2task = {}

    def _get_task(self, view_id):
        _task = None
        if view_id not in self.view_id2task:
            from twisted.internet import task

            _task = task.LoopingCall(main.run_every_second(view_id))
            self.view_id2task[view_id] = _task
        else:
            _task = self.view_id2task[view_id]
        return _task

    @staticmethod
    def _preconditions(view_id):
        if view_id is None:
            raise TypeError('"view_id" must be not None')

    def run(self, listening=None, view_id=None):
        self._preconditions(view_id)
        _task = self._get_task(view_id)

        if listening == 'start':
            if not _task.running:
                _task.start(1.0)
        elif listening == 'stop':
            if _task.running:
                _task.stop()
        else:
            raise TypeError('"listening" argument legal values are "start" or "stop".')


def terminate_collaboration(view_id):
    assert Collaboration
    sublime.run_command('collaboration', {'listening': 'stop', 'view_id': view_id})
    if view_id in registry:
        del registry[view_id]