# coding=utf-8
"""
Тест на что-то
"""
from twisted.internet import defer
from twisted.internet.endpoints import clientFromString, serverFromString
from twisted.internet.protocol import Factory
from twisted.protocols.amp import AMP, CommandLocator, Command, String, Boolean
from twisted.trial import unittest
import test.base.constants as constants

__author__ = 'snowy'


def PatchIsNotApplicable(Exception):
    pass


class Patch(String):
    pass


class ApplyPatchCommand(Command):
    arguments = [('patch', Patch())]
    response = [('succeed', Boolean())]
    errors = {PatchIsNotApplicable: 'PatchIsNotApplicable, maybe try one more time'}


class DiffMatchPatchAlgorithm(CommandLocator):
    def __init__(self, initialText):
        self.initialText = initialText

    @ApplyPatchCommand.responder
    def applyRemotePatch(self, patch):
        
        return {'succeed': True}


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
        factory = Factory.forProtocol(lambda: AMP(locator=DiffMatchPatchAlgorithm(constants.initialText)))
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
        serverInitialized = self.initServer()
        return serverInitialized.addCallback(lambda ignore: self.initClient())

    def tearDown(self):
        d = defer.maybeDeferred(self.serverPort.stopListening)
        self.clientProtocol.transport.loseConnection()
        return d

    def test_base(self):
        return self.clientProtocol.callRemote(ApplyPatchCommand, patch=constants.patch) \
            .addCallback(self.assertTrue, msg='Патч не может быть применен')


if __name__ == '__main__':
    unittest.main()
