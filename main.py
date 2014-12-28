# coding=utf-8
from twisted.internet import reactor

from core.core import NetworkApplicationConfig, Application


__author__ = 'snowy'


def init():
    cfg1 = NetworkApplicationConfig(serverConnString=b'tcp:0',
                                    clientConnString=b'tcp:host=localhost')
    cfg2 = NetworkApplicationConfig(serverConnString=b'tcp:0',
                                    clientConnString=b'tcp:host=localhost')
    app1 = Application(reactor)
    app2 = Application(reactor)
    app1.algorithm.local_text = app2.algorithm.local_text = 'initialText'

    # create app1server and app2client
    app1.setUpServer(cfg1) \
        .addCallback(lambda listeningPort: cfg2.appendClientPort(listeningPort.getHost().port)) \
        .addCallback(lambda _cfg2: app2.setUpClient(_cfg2))

    # create app2server and app1client
    app2.setUpServer(cfg2) \
        .addCallback(lambda listeningPort: cfg1.appendClientPort(listeningPort.getHost().port)) \
        .addCallback(lambda _cfg1: app2.setUpClient(_cfg1))


init()
reactor.run()
