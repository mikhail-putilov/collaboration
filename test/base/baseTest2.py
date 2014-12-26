# coding=utf-8
"""
Пинг-понг тест с использованием callbacks
"""
from twisted.internet.endpoints import clientFromString
from twisted.internet.protocol import ClientFactory
from twisted.protocols.amp import AMP

from test.base.baseTest1 import PongLocator, PingPongCommand


__author__ = 'snowy'
from twisted.internet import defer, protocol
from twisted.trial import unittest


class ServerProtocolStub(AMP):
    def connectionLost(self, reason):
        super(ServerProtocolStub, self).connectionLost(reason)
        self.factory.onConnectionLost.callback(self)


class ClientProtocolStub(AMP):
    def connectionMade(self):
        super(ClientProtocolStub, self).connectionMade()
        # self.factory.onConnectionMade.callback(self)

    def connectionLost(self, reason):
        super(ClientProtocolStub, self).connectionLost(reason)
        self.factory.onConnectionLost.callback(self)


class TestDisconnect(unittest.TestCase):
    def save(self, key, value):
        setattr(self, key, value)
        return value

    def setUp(self):
        from twisted.internet import reactor

        self.reactor = reactor
        ":type reactor: twisted.internet.selectreactor.SelectReactor"

        self.serverDisconnected = defer.Deferred()
        self.serverPort = self._listenServer(self.serverDisconnected)
        self.clientDisconnected = defer.Deferred()
        return self._connectClient(self.clientDisconnected).addCallback(
            lambda proto: self.save("clientProtocol", proto))

    def _listenServer(self, d):
        """
        Начать слушать порт на сервере
        :param d: defer.Deferred который вызывается при connectionLost
        :return: defer.Deferred с результатом Port
        """

        f = protocol.Factory()
        f.onConnectionLost = d
        f.protocol = lambda: ServerProtocolStub(locator=PongLocator())
        return self.reactor.listenTCP(0, f)

    def _connectClient(self, d2):
        """
        Подключиться к серверу
        :param d2: defer.Deferred вызываемый при connectionLost
        :return: defer.Deferred с результатом подключения (инициализированный протокол ClientProtocolStub)
        """
        factory = ClientFactory.forProtocol(ClientProtocolStub)
        factory.onConnectionLost = d2
        return clientFromString(self.reactor, b"tcp:host=localhost:port={0}".format(self.serverPort.getHost().port)) \
            .connect(factory)

    def tearDown(self):
        d = defer.maybeDeferred(self.serverPort.stopListening)
        self.clientProtocol.transport.loseConnection()
        return defer.gatherResults([d,
                                    self.clientDisconnected,
                                    self.serverDisconnected])

    def test_disconnect(self):
        def print_it(it):
            print it

        return self.clientProtocol.callRemote(PingPongCommand, ping='ping').addCallback(print_it)


