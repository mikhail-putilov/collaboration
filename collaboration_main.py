# coding=utf-8
import os
import platform
import sys

# this assures we use the included libs/twisted and libs/zope libraries
# this is of particular importance on Mac OS X since an older version of twisted
# is already installed in the OS
__file__ = os.path.normpath(os.path.abspath(__file__))
__path__ = os.path.dirname(__file__)
libs_path = os.path.join(__path__, 'libs')
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

# need the windows select.pyd binary
from twisted.python import runtime

__file__ = os.path.normpath(os.path.abspath(__file__))
__path__ = os.path.dirname(__file__)
if runtime.platform.isWindows():
    libs_path = os.path.join(__path__, 'libs', 'win', platform.architecture()[0])
    if libs_path not in sys.path:
        sys.path.insert(0, libs_path)
elif runtime.platform.isLinux():
    libs_path = os.path.join(__path__, 'libs', 'linux', platform.architecture()[0])
    if libs_path not in sys.path:
        sys.path.insert(0, libs_path)
elif runtime.platform.isMacOSX():
    libs_path = os.path.join(__path__, 'libs', 'mac', platform.architecture()[0])
    if libs_path not in sys.path:
        sys.path.insert(0, libs_path)

# --- configure logging system --- #
import logging
import logging.config

logging.config.fileConfig('logging.cfg', disable_existing_loggers=False)
# --- ------------------------ --- #

logger = logging.getLogger("collaboration")

import sublime

# wrapper function to the entrypoint into the sublime main loop


def callInSublimeLoop(funcToCall):
    sublime.set_timeout(funcToCall, 0)

# --- install and start the twisted reactor, if it hasn't already be started --- #
from twisted.internet.error import ReactorAlreadyInstalledError, ReactorAlreadyRunning, ReactorNotRestartable

reactorAlreadyInstalled = False
try:
    from twisted.internet import _threadedselect

    _threadedselect.install()
except ReactorAlreadyInstalledError:
    reactorAlreadyInstalled = True

from twisted.internet import reactor

try:
    reactor.interleave(callInSublimeLoop, installSignalHandlers=False)
except ReactorAlreadyRunning:
    reactorAlreadyInstalled = True
except ReactorNotRestartable:
    reactorAlreadyInstalled = True

if reactorAlreadyInstalled:
    print 'reactorAlreadyInstalled'
    logger.debug('twisted reactor already installed')
    if type(reactor) != _threadedselect.ThreadedSelectReactor:
        logger.warn('unexpected reactor type installed: %s, it is best to use twisted.internet._threadedselect!' % type(
            reactor))
else:
    print 'not reactorAlreadyInstalled'
    logger.debug('twisted reactor installed and running')
# --- --------------------------------------------------------------------- --- #
from collab.core.core import *
import sublime, sublime_plugin

registry = {}


class ClientConnectionStringIsNotInitializedError(Exception):
    pass


class RunServerCommand(sublime_plugin.TextCommand):
    # noinspection PyUnusedLocal
    def run(self, edit):
        """
        Начальная инициализация серверной части.
        """
        app = Application(reactor, name='application{0}'.format(self.view.id()), view=self.view)
        # print 'app has created: id={0}; title={1}'.format(app.name, self.view.name())

        def _cb(client_connection_string):
            registry[self.view.id()] = (app, client_connection_string)
            print 'client_connection_string={0}'.format(client_connection_string)

        app.setUpServerFromStr('tcp:0').addCallback(_cb)


class RunClientCommand(sublime_plugin.TextCommand):
    # noinspection PyUnusedLocal
    def run(self, edit, conn_str=None):
        """
        Начальная инициализация серверной части.
        """
        if conn_str is None:
            raise ClientConnectionStringIsNotInitializedError()
        app, _ = registry[self.view.id()]
        app.connectAsClientFromStr(conn_str) \
            .addCallback(lambda ignore: sublime.status_message("client has connected"))


class MainDispatcherListener(sublime_plugin.EventListener):
    def on_modified(self, view):
        if view.id() in registry:
            app, _ = registry[view.id()]
            allTextRegion = sublime.Region(0, view.size())
            allText = view.substr(allTextRegion)
            app.algorithm.local_onTextChanged(allText)


