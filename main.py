# coding=utf-8
from twisted.internet import reactor

from core.core import NetworkApplicationConfig, Application


__author__ = 'snowy'


def print_it(arg):
    print arg
    return arg


def main():
    global print_it, app, initServer, initClient

    app = Application(reactor)

    def initServer():
        cfg = NetworkApplicationConfig(serverConnString=b'tcp:0')

        return app.setUpServer(cfg) \
            .addCallback(lambda listeningPort: listeningPort.getHost().port) \
            .addCallback(print_it)

    def initClient(port):
        cfg = NetworkApplicationConfig(clientConnString=b'tcp:host=localhost:{0}'.format(port))
        return app.setUpClient(cfg)

    initServer()
    reactor.run()


if __name__ == '__main__':
    main()
