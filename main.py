# coding=utf-8

import sublime_plugin
import sublime
from collections import namedtuple

RegistryEntry = namedtuple('RegistryEntry', ['application', 'connection_string'])

from core.core import *
from reactor import reactor

registry = {}
''':type registry: dict which maps "view_id" → (view's application, view's client_connection_string)'''


class ClientConnectionStringIsNotInitializedError(Exception):
    pass


class ViewAwareApplication(Application):
    def __init__(self, _reactor, view, name=''):
        super(ViewAwareApplication, self).__init__(_reactor, name)
        self.view = view
        ':type view: sublime.View'
        self.locator = ViewAwareAlgorithm(self.view, clientProtocol=self.clientProtocol, name=name)


class ViewAwareAlgorithm(DiffMatchPatchAlgorithm):
    def __init__(self, view, initialText='', clientProtocol=None, name=''):
        """
        Алгоритм, который знает о том, что работает с sublime.View
        :param view: sublime.View
        :param initialText: str
        :param clientProtocol:
        :param name: str
        """
        super(ViewAwareAlgorithm, self).__init__(initialText, clientProtocol, name)
        self.view = view
        ':type view: sublime.View'

    @ApplyPatchCommand.responder
    def remote_applyPatch(self, patch):
        # noinspection PyArgumentList
        edit = self.view.begin_edit()
        try:
            log.msg('Current text before patching({0}): {1}'.format(self.name, self.currentText),
                    logLevel=logging.DEBUG)
            respond = super(ViewAwareAlgorithm, self).remote_applyPatch(patch)
            self.view.erase(edit, sublime.Region(0, self.view.size()))
            self.view.insert(edit, 0, self.currentText)
            return respond
        finally:
            self.view.end_edit(edit)


class ViewIsNotInitializedError(Exception):
    pass


# noinspection PyClassHasNoInit
class RunServerCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        """
        Начальная инициализация серверной части.
        """
        app = ViewAwareApplication(reactor, self.view, name='Application{0}'.format(self.view.id()))
        log.msg('App is created for the view(id={0})'.format(self.view.id()))

        def _cb(client_connection_string):
            registry[self.view.id()] = RegistryEntry(app, client_connection_string)
            log.msg('client_connection_string={0}'.format(client_connection_string), logLevel=logging.DEBUG)

        app.setUpServerFromStr('tcp:0').addCallback(_cb)


# noinspection PyClassHasNoInit
class RunClientCommand(sublime_plugin.TextCommand):
    def run(self, edit, connection_str=None):
        """
        Начальная инициализация серверной части.
        """
        if connection_str is None:
            raise ClientConnectionStringIsNotInitializedError()
        app = registry[self.view.id()].application
        app.connectAsClientFromStr(connection_str) \
            .addCallback(lambda ignore: log.msg('The client has connected to the view(id={0})'.format(self.view.id())))

# todo: костыль, не понятно как его убрать. При редактировании текста, срабатывает два раза on_modified ивент
allowedToSendModifications = True


# noinspection PyClassHasNoInit
class MainDispatcherListener(sublime_plugin.EventListener):
    def on_modified(self, view):
        """

        :param view: sublime.View
        """
        global allowedToSendModifications
        allowedToSendModifications = not allowedToSendModifications
        if view.id() in registry and allowedToSendModifications:
            app = registry[view.id()].application
            allTextRegion = sublime.Region(0, view.size())
            allText = view.substr(allTextRegion)
            app.algorithm.local_onTextChanged(allText)


class NumberOfWindowsIsNotSupportedError(Exception):
    pass


# noinspection PyClassHasNoInit
class ConnectTwoWindows(sublime_plugin.TextCommand):
    """
    Соединить два окна. Иницилизирует два пира, каждый из которых владеет одним окном ST.
    Текст в обоих окнах должен синхронизироваться
    """

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