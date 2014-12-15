# coding=utf-8
__author__ = 'snowy'

from twisted.internet.protocol import Factory, Protocol
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet import reactor


class QOTD(Protocol):
    def __init__(self):
        pass

    def connectionMade(self):
        self.transport.write("An apple a day keeps the doctor away\r\n")
        self.transport.loseConnection()


class QOTDFactory(Factory):
    def __init__(self):
        pass

    def buildProtocol(self, addr):
        return QOTD()

# 8007 is the port you want to run under. Choose something >1024
endpoint = TCP4ServerEndpoint(reactor, 8007)
endpoint.listen(QOTDFactory())
reactor.run()