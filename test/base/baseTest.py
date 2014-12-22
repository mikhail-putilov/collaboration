# coding=utf-8
from twisted.internet.endpoints import connectProtocol, clientFromString, serverFromString
from twisted.internet.protocol import ClientCreator, Factory
from twisted.protocols.amp import AMP, CommandLocator, Command

__author__ = 'snowy'

from twisted.trial import unittest


class GivenNotPingException(Exception):
    pass


class PingPongCommand(Command):
    arguments = [('ping', 'ping')]
    response = [('pong', 'pong')]


class PongLocator(CommandLocator):
    def __init__(self):
        pass

    @staticmethod
    @PingPongCommand.responder
    def ping(ping):
        if ping != "ping":
            raise GivenNotPingException()
        return "pong"


class BaseTest(unittest.TestCase):
    def setUp(self):
        from twisted.internet import reactor

        self.reactor = reactor
        self.serverEndpoint = serverFromString(self.reactor, b"tcp:9879")
        self.protocol = self.serverEndpoint.listen(Factory.forProtocol(AMP))

    def testBasicCallback(self):
        """При отрправке сообщения Ping, должно возращаться сообщение Pong"""
        clientEndpoint = clientFromString(self.reactor, b"tcp:host=localhost:port=9879")
        self.protocol.addCallback(lambda ignore: connectProtocol(endpoint=clientEndpoint, protocol=AMP))


if __name__ == '__main__':
    unittest.main()
