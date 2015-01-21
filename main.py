# coding=utf-8
import logging
import os
import sys
import sublime

# noinspection PyUnboundLocalVariable
__file__ = os.path.normpath(os.path.abspath(__file__))
__path__ = os.path.dirname(__file__)
libs_path = os.path.join(__path__, 'libs')
twisted_path = os.path.join(__path__, 'libs', 'twisted')
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)
if twisted_path not in sys.path:
    sys.path.insert(0, twisted_path)

from twisted.python import log
log.startLogging(sys.stdout)


def callInSublimeLoop(funcToCall):
    sublime.set_timeout(funcToCall, 0)


from twisted.internet.error import ReactorAlreadyInstalledError, ReactorAlreadyRunning, ReactorNotRestartable

reactorAlreadyInstalled = False
try:
    # noinspection PyProtectedMember
    from twisted.internet import _threadedselect

    _threadedselect.install()
except ReactorAlreadyInstalledError:
    reactorAlreadyInstalled = True

from twisted.internet import reactor

try:
    # noinspection PyUnresolvedReferences
    reactor.interleave(callInSublimeLoop, installSignalHandlers=False)
except ReactorAlreadyRunning:
    reactorAlreadyInstalled = True
except ReactorNotRestartable:
    reactorAlreadyInstalled = True

if reactorAlreadyInstalled:
    log.msg('twisted reactor already installed', logLevel=logging.DEBUG)
    if type(reactor) != _threadedselect.ThreadedSelectReactor:
        log.msg('unexpected reactor type installed: %s, it is best to use twisted.internet._threadedselect!' % type(
            reactor), logLevel=logging.WARNING)
else:
    log.msg('twisted reactor installed and running', logLevel=logging.DEBUG)
# --- --------------------------------------------------------------------- --- #
from core.core import *

import sublime_plugin

registry = {}
"""
Реестр - мапа из view_id -> (view's app, view's client_connection_string)
"""


class ClientConnectionStringIsNotInitializedError(Exception):
    pass


# noinspection PyClassHasNoInit
class RunServerCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        """
        Начальная инициализация серверной части.
        """
        app = Application(reactor, name='Application{0}'.format(self.view.id()))
        log.msg('App is created for the view(id={0})'.format(self.view.id()))

        def _cb(client_connection_string):
            registry[self.view.id()] = (app, client_connection_string)
            log.msg('client_connection_string={0}'.format(client_connection_string), logLevel=logging.DEBUG)

        app.setUpServerFromStr('tcp:0').addCallback(_cb)


# noinspection PyClassHasNoInit
class RunClientCommand(sublime_plugin.TextCommand):
    def run(self, edit, conn_str=None):
        """
        Начальная инициализация серверной части.
        """
        if conn_str is None:
            raise ClientConnectionStringIsNotInitializedError()
        app, _ = registry[self.view.id()]
        app.connectAsClientFromStr(conn_str) \
            .addCallback(lambda ignore: log.msg("The client has connected to the view(id={0})".format(self.view.id())))


# noinspection PyClassHasNoInit
class MainDispatcherListener(sublime_plugin.EventListener):
    def on_modified(self, view):
        if view.id() in registry:
            app, _ = registry[view.id()]
            allTextRegion = sublime.Region(0, view.size())
            allText = view.substr(allTextRegion)
            app.algorithm.local_onTextChanged(allText)

