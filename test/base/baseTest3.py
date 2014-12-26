# coding=utf-8
"""
Тесты на основную функциональность
"""
from twisted.internet import defer
from twisted.internet.endpoints import clientFromString, serverFromString
from twisted.internet.protocol import Factory
from twisted.protocols.amp import AMP, CommandLocator, Command, Boolean, Unicode
from twisted.trial import unittest

from libs.dmp import diff_match_patch
import test.base.constants as constants


__author__ = 'snowy'


class Patch(Unicode):
    pass


class NoTextAvailableException(Exception):
    pass


def PatchIsNotApplicableException(Exception):
    pass


class GetTextCommand(Command):
    response = [('text', Unicode())]
    errors = {NoTextAvailableException: 'Невозможно получить текст'}


class ApplyPatchCommand(Command):
    arguments = [('patch', Patch())]
    response = [('succeed', Boolean())]
    errors = {PatchIsNotApplicableException: 'Патч не может быть применен'}


class DiffMatchPatchAlgorithm(CommandLocator):
    clientProtocol = None

    def __init__(self, initialText):
        self.currentText = initialText
        self.dmp = diff_match_patch()

    @property
    def text(self):
        return self.currentText

    def setText(self, text):
        """
        Заменить текущий текст без сайд-эффектов
        :param text: str
        """
        self.currentText = text

    def onTextChanged(self, nextText):
        """
        Установить текст, посчитать дельту, отправить всем участникам сети патч
        :param nextText: текст, который является более новой версией текущего текст self.currentText
        """
        patches = self.dmp.patch_make(self.currentText, nextText)
        serialized = self.dmp.patch_toText(patches)
        return self.clientProtocol.callRemote(ApplyPatchCommand, patch=serialized)

    @ApplyPatchCommand.responder
    def applyRemotePatch(self, patch):
        _patch = self.dmp.patch_fromText(patch)
        patchedText, result = self.dmp.patch_apply(_patch, self.currentText)
        if False in result:
            return {'succeed': False}
        self.currentText = patchedText
        return {'succeed': True}

    @GetTextCommand.responder
    def getTextRemote(self):
        if self.text is None:
            raise NoTextAvailableException()
        return {'text': self.text}


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

    def test_sequential(self):
        """
        Тестирование последовательного изменения текста с блокировками (пока не будет применены изменения на сервере,
        клиент ждет)
        """
        alg = DiffMatchPatchAlgorithm(constants.textVersionSeq[0])
        alg.clientProtocol = self.clientProtocol
        # emulate editing text
        d = defer.succeed(None)
        for newTextVersion in constants.textVersionSeq[1:]:
            d = d.addCallback(lambda ignore: alg.onTextChanged(newTextVersion)) \
                .addCallback(self.assertTrue, msg='Патчи textVersionSeq должены примениться на сервере')

        def checkResult(ignore):
            return self.clientProtocol \
                .callRemote(GetTextCommand) \
                .addCallback(self.assertDictContainsSubset,
                             {'text': constants.textVersionSeq[-1]},
                             msg='Результат применения патчей на сервере должен привести '
                                 'к тому же состоянию текста textVersionSeq[-1]')

        return d.addCallback(checkResult)


if __name__ == '__main__':
    unittest.main()
