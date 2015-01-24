import logging

__author__ = 'snowy'
import sublime
from twisted.python import log


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