# coding=utf-8
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


class PongLocator(CommandLocator):
    def __init__(self):
        pass

    @staticmethod
    @PingPongCommand.responder
    def ping1(ping):
        if ping != "ping":
            raise GivenNotPingException()
        return "pong"


class BaseTest(unittest.TestCase):
    def save(self, key, value):
        setattr(self, key, value)
        return value

    def setUp(self):
        from twisted.internet import reactor

        self.reactor = reactor
        self.serverEndpoint = serverFromString(self.reactor, b"tcp:9879")
        factory = Factory.forProtocol(lambda: AMP(locator=PingPongCommand()))
        return self.serverEndpoint.listen(factory).addCallback(lambda p: self.save('serverPort', p))

    def testBasicCallback(self):
        """При отрправке сообщения Ping, должно возращаться сообщение Pong"""

        def x(y):
            return y.transport.loseConnection()

        clientEndpoint = clientFromString(self.reactor, b"tcp:host=localhost:port=9879")
        protocolFactory = Factory.forProtocol(AMP)
        return clientEndpoint.connect(protocolFactory). \
            addCallback(x)

    def tearDown(self):
        d = defer.maybeDeferred(self.serverPort.stopListening)
        return defer.gatherResults([d,
                                    self.clientDisconnected,
                                    self.serverDisconnected])


if __name__ == '__main__':
    unittest.main()
