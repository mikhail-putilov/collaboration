# coding=utf-8
"""
Тесты на основную функциональность
"""
from twisted.internet import defer
from twisted.internet.endpoints import clientFromString, serverFromString
from twisted.internet.protocol import Factory
from twisted.protocols.amp import AMP
from twisted.trial import unittest
from twisted.python import log

from core.core import DiffMatchPatchAlgorithm
from core.other import save
from core.command import GetTextCommand
import test.base.constants as constants


__author__ = 'snowy'


class BaseTest(unittest.TestCase):
    def initServer(self):
        """
        Инициализация сервера
        :return : defer.Deferred
        """
        self.serverEndpoint = serverFromString(self.reactor, b'tcp:9879')
        factory = Factory.forProtocol(
            lambda: AMP(locator=DiffMatchPatchAlgorithm(None, initialText=constants.initialText)))
        savePort = lambda p: save(self, 'serverPort', p)  # given port
        return self.serverEndpoint.listen(factory).addCallback(savePort)

    def initClient(self):
        """
        Инициализация клиента
        :return : defer.Deferred
        """
        clientEndpoint = clientFromString(self.reactor, b'tcp:host=localhost:port=9879')
        protocolFactory = Factory.forProtocol(AMP)
        saveProtocol = lambda p: save(self, 'clientProtocol', p)  # given protocol
        return clientEndpoint.connect(protocolFactory).addCallback(saveProtocol)

    def setUp(self):
        from twisted.internet import reactor

        self.reactor = reactor
        serverInitialized = self.initServer()
        return serverInitialized.addCallback(lambda ignore: self.initClient())

    def tearDown(self):
        d = defer.maybeDeferred(self.serverPort.stopListening)
        self.clientProtocol.transport.loseConnection()
        return d

    def test_sequential(self):
        """
        Тестирование последовательного изменения текста с блокировками (пока не будет применены изменения на сервере,
        клиент ждет)
        """
        alg = DiffMatchPatchAlgorithm(None, initialText=constants.textVersionSeq[0], clientProtocol=self.clientProtocol)
        # emulate editing text
        d = defer.succeed(None)
        for newTextVersion in constants.textVersionSeq[1:]:
            iteration = lambda ignore, text: alg.local_onTextChanged(text)
            d = d.addCallback(iteration, newTextVersion)

        def checkResult(ignore):
            return self.clientProtocol \
                .callRemote(GetTextCommand) \
                .addCallback(self.assertDictContainsSubset,
                             {'text': constants.textVersionSeq[-1]},
                             msg='Результат применения патчей на сервере должен привести '
                                 'к тому же состоянию текста textVersionSeq[-1]')

        return d.addCallback(checkResult).addErrback(log.err)


if __name__ == '__main__':
    unittest.main()
