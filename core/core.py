# coding=utf-8
from twisted.protocols.amp import Command, Unicode, Boolean, CommandLocator
from twisted.internet import defer
from twisted.internet.endpoints import serverFromString, clientFromString
from twisted.internet.protocol import Factory, ClientFactory
from twisted.protocols.amp import AMP

from libs.dmp import diff_match_patch


__author__ = 'snowy'


def save(self, key, value):
    setattr(self, key, value)
    return value


class Patch(Unicode):
    pass


class NoTextAvailableException(Exception):
    pass


def PatchIsNotApplicableException():
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

    def __init__(self, initialText=''):
        self.currentText = initialText
        self.dmp = diff_match_patch()

    @property
    def local_text(self):
        return self.currentText

    def local_setText(self, text):
        """
        Заменить текущий текст без сайд-эффектов
        :param text: str
        """
        self.currentText = text

    def local_onTextChanged(self, nextText):
        """
        Установить текст, посчитать дельту, отправить всем участникам сети патч
        :param nextText: str текст, который является более новой версией текущего текст self.currentText
        """
        patches = self.dmp.patch_make(self.currentText, nextText)
        serialized = self.dmp.patch_toText(patches)
        return self.clientProtocol.callRemote(ApplyPatchCommand, patch=serialized)

    @ApplyPatchCommand.responder
    def remote_applyPatch(self, patch):
        _patch = self.dmp.patch_fromText(patch)
        patchedText, result = self.dmp.patch_apply(_patch, self.currentText)
        if False in result:
            return {'succeed': False}
        self.currentText = patchedText
        return {'succeed': True}

    @GetTextCommand.responder
    def remote_getText(self):
        if self.local_text is None:
            raise NoTextAvailableException()
        return {'text': self.local_text}


class NetworkApplicationConfig(object):
    def __init__(self, serverConnString=None, clientConnString=None):
        """
        Конфиг сетевого подключения приложения
        :param serverConnString: str строка подключения для serverFromString
        :param clientConnString: str строка подключения для clientFromString
        """
        self.clientConnString = clientConnString
        self.serverConnString = serverConnString


class Application(object):
    def __init__(self, reactor):
        self.reactor = reactor
        self.locator = DiffMatchPatchAlgorithm()
        # заполняются после setUp():
        self.serverEndpoint = None
        self.serverFactory = None
        self.clientFactory = None
        self.serverPort = None
        self.clientProtocol = None

    def _initServer(self, locator, serverConnString):
        """
        Инициализация сервера
        :type serverConnString: str строка подключения для serverFromString
        :return : defer.Deferred
        """
        self.serverEndpoint = serverFromString(self.reactor, serverConnString)
        savePort = lambda p: save(self, 'serverPort', p)  # given port
        self.serverFactory = Factory.forProtocol(lambda: AMP(locator=locator))
        return self.serverEndpoint.listen(self.serverFactory).addCallback(savePort)

    def _initClient(self, clientConnString):
        """
        Инициализация клиента
        :type clientConnString: str строка подключения для clientFromString
        :return : defer.Deferred
        """
        clientEndpoint = clientFromString(self.reactor, clientConnString)
        saveProtocol = lambda p: save(self, 'clientProtocol', p)  # given protocol
        self.clientFactory = ClientFactory.forProtocol(AMP)
        return clientEndpoint.connect(self.clientFactory).addCallback(saveProtocol)

    def setUp(self, cfg):
        """
        Инициализировать сервер и клиент
        :type cfg: NetworkApplicationConfig конфиг сети
        :rtype : defer.Deferred
        """
        serverInitialized = self._initServer(self.locator, cfg.serverConnString)
        clientInitialized = self._initClient(cfg.clientConnString)
        return defer.gatherResults([serverInitialized, clientInitialized])

    def tearDown(self):
        d = defer.maybeDeferred(self.serverPort.stopListening)
        self.clientProtocol.transport.loseConnection()
        return d