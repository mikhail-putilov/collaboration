# coding=utf-8
"""
Пинг-понг тест с использованием endpoints
"""
from twisted.internet import defer
from twisted.internet.endpoints import clientFromString, serverFromString
from twisted.internet.protocol import Factory
from twisted.protocols.amp import AMP, CommandLocator, Command, String

__author__ = 'snowy'

from twisted.trial import unittest


class GivenNotPingException(Exception):
    pass


class PingPongCommand(Command):
    arguments = [('ping', String())]
    response = [('pong', String())]
    errors = {GivenNotPingException: 'GivenNotPingException'}


class PongLocator(CommandLocator):
    def __init__(self):
        pass

    @PingPongCommand.responder
    def ping1(self, ping):
        if ping != 'ping':
            raise GivenNotPingException()
        return {'pong': 'pong'}


class BaseTest(unittest.TestCase):
    def save(self, key, value):
        setattr(self, key, value)
        return value

    def initServer(self):
        """
        Инициализация сервера
        :return : defer.Deferred
        """
        self.serverEndpoint = serverFromString(self.reactor, b"tcp:9879")
        factory = Factory.forProtocol(lambda: AMP(locator=PongLocator()))
        savePort = lambda p: self.save('serverPort', p)  # given port
        return self.serverEndpoint.listen(factory).addCallback(savePort)

    def initClient(self):
        """
        Инициализация клиента
        :return : defer.Deferred
        """
        clientEndpoint = clientFromString(self.reactor, b"tcp:host=localhost:port=9879")
        protocolFactory = Factory.forProtocol(AMP)
        saveProtocol = lambda p: self.save('clientProtocol', p)  # given protocol
        return clientEndpoint.connect(protocolFactory).addCallback(saveProtocol)

    def setUp(self):
        from twisted.internet import reactor

        self.reactor = reactor
        serverDeferred = self.initServer()
        return serverDeferred.addCallback(lambda ignore: self.initClient())

    def tearDown(self):
        d = defer.maybeDeferred(self.serverPort.stopListening)
        self.clientProtocol.transport.loseConnection()
        return d

    def test_a(self):
        return self.clientProtocol.callRemote(PingPongCommand, ping='ping').addCallback(self.assertDictContainsSubset,
                                                                                        {'pong': 'pong'},
                                                                                        'Пришел не понг ответ')


if __name__ == '__main__':
    unittest.main()
