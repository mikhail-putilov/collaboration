# coding=utf-8
from twisted.internet import reactor
from twisted.internet.defer import gatherResults

from core.core import NetworkApplicationConfig, Application


__author__ = 'snowy'

app1 = Application(reactor, 'app1')
app2 = Application(reactor, 'app2')


def init():
    cfg1 = NetworkApplicationConfig(serverConnString=b'tcp:0',
                                    clientConnString=b'tcp:host=localhost')
    cfg2 = NetworkApplicationConfig(serverConnString=b'tcp:0',
                                    clientConnString=b'tcp:host=localhost')

    # create app1server and app2client
    d1 = app1.setUpServer(cfg1) \
        .addCallback(lambda listeningPort: cfg2.appendClientPort(listeningPort.getHost().port)) \
        .addCallback(lambda _cfg2: app2.setUpClient(_cfg2))

    # create app2server and app1client
    d2 = app2.setUpServer(cfg2) \
        .addCallback(lambda listeningPort: cfg1.appendClientPort(listeningPort.getHost().port)) \
        .addCallback(lambda _cfg1: app1.setUpClient(_cfg1))
    return gatherResults([d1, d2])


textVersions = ['ver', 'v', 'vrso1', 'version1viva']


def text_changed(app, text):
    """
    Эмулирование работы текстового редактора
    :type app: Application
    """
    print '---'
    app.algorithm.local_onTextChanged(text)
    app.algorithm.local_text = text


def pretty_print(app, annotation):
    """
    Результат работы
    :param app:
    :param annotation:
    """
    print annotation
    print app.algorithm.local_text


def test(ignore):
    for i, text in enumerate(textVersions):
        chosenPeer = app1 if i % 2 == 0 else app2
        reactor.callLater(i+1, text_changed, chosenPeer, text)

    reactor.callLater(6, pretty_print, app1, '\napp1:')
    reactor.callLater(6, pretty_print, app2, '\napp2:')


d = init()
d.addCallback(test)

reactor.run()