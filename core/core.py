# coding=utf-8
"""
Основная функциональность. Инкапсулировано от sublime.
Вся бизнес-работа выполняется на основе diff_match_patch объекта.
"""
import logging
import time

import ntplib
from twisted.protocols.amp import CommandLocator
from twisted.internet import defer
from twisted.internet.endpoints import serverFromString, clientFromString
from twisted.internet.protocol import Factory, ClientFactory
from twisted.protocols.amp import AMP
from twisted.python import log

from command import *
from exceptions import *
from other import save
from libs.dmp import diff_match_patch
import history


__author__ = 'snowy'


class DiffMatchPatchAlgorithm(CommandLocator):
    def __init__(self, history_line, initialText='', clientProtocol=None, name=''):
        self.name = name
        self.clientProtocol = clientProtocol
        self.currentText = initialText
        self.dmp = diff_match_patch()
        self.history_line = history_line
        c = ntplib.NTPClient()
        response = c.request('europe.pool.ntp.org', version=3)
        self.global_delta = response.tx_time - time.time()

    def _get_current_timestamp(self):
        if self.global_delta is None:
            self.global_delta = self._get_global_delta()
        return time.time() + self.global_delta

    @staticmethod
    def _get_global_delta():
        c = ntplib.NTPClient()
        response = c.request('europe.pool.ntp.org', version=3, timeout=10)
        return response.tx_time - time.time()

    def _alter_forward_lamport_time(self, delta_time):
        """
        Подкрутить время вперед на часах Лампорта
        :param delta_time: float время в секундах (доли тоже считаются)
        :raise GlobalDeltaIsNotInited:
        """
        assert delta_time > 0
        if self.global_delta is None:
            raise GlobalDeltaIsNotInitedException('Field "self.global_delta" must be inited before.'
                                                  'Set it with _get_global_delta method')
        self.global_delta += delta_time

    @property
    def local_text(self):
        return self.currentText

    @local_text.setter
    def local_text(self, text):
        """
        Заменить текущий текст без сайд-эффектов
        :param text: str
        """
        self.currentText = text

    def local_onTextChanged(self, nextText):
        """
        Установить текст, посчитать дельту, отправить всем участникам сети патч
        :rtype : defer.Deferred с результатом команды ApplyPatchCommand
        :param nextText: str текст, который является более новой версией текущего текста self.currentText
        """
        patches = self.dmp.patch_make(self.currentText, nextText)
        if not patches:
            return ApplyPatchCommand.no_work_is_done_response

        self.currentText = nextText

        if self.clientProtocol is None:
            log.msg('Client protocol is None', logLevel=logging.DEBUG)
            return ApplyPatchCommand.no_work_is_done_response

        serialized = self.dmp.patch_toText(patches)

        patch_is_not_empty_and_we_have_clients = serialized and self.clientProtocol is not None
        if patch_is_not_empty_and_we_have_clients:
            log.msg('{0}: sending patch:\n<patch>\n{1}</patch>'.format(self.name, serialized), logLevel=logging.DEBUG)
            return self.clientProtocol.callRemote(ApplyPatchCommand, patch=serialized,
                                                  timestamp=time.time() + self.global_delta)

        return ApplyPatchCommand.no_work_is_done_response

    @ApplyPatchCommand.responder
    def remote_applyPatch(self, patch, timestamp):
        _patch = self.dmp.patch_fromText(patch)
        patchedText, result = self.dmp.patch_apply(_patch, self.currentText)
        if False in result:
            log.msg('{0}: remote patch is not applied'.format(self.name), logLevel=logging.DEBUG)
            raise PatchIsNotApplicableException()

        log.msg('{0}: <before.model>{1}</before.model>'.format(self.name, self.currentText),
                logLevel=logging.DEBUG)

        self.currentText = patchedText

        log.msg('{0}: <after.model>{1}</after.model>'.format(self.name, self.currentText),
                logLevel=logging.DEBUG)
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
        ":type clientConnString: str"
        self.serverConnString = serverConnString
        ":type serverConnString: str"

    def appendClientPort(self, port):
        self.clientConnString += ':port={0}'.format(port)
        return self


class Application(object):
    def __init__(self, reactor, name=''):
        self.reactor = reactor
        self.name = name
        # заполняются после setUp():
        self.serverEndpoint = None
        self.serverFactory = None
        self.clientFactory = None
        self.serverPort = None
        self.clientProtocol = None
        self.history_line = history.HistoryLine(self)  # todo: maybe remove history
        self.locator = DiffMatchPatchAlgorithm(self.history_line, clientProtocol=self.clientProtocol, name=name)

    @property
    def serverPortNumber(self):
        if self.serverPort is None:
            raise ServerPortIsNotInitializedError()
        return self.serverPort.getHost().port

    @property
    def algorithm(self):
        """
        Основной алгоритм, который реагирует на изменения текста
        отправляет данные другим участникам и пр.
        :return: DiffMatchPatchAlgorithm
        """
        return self.locator

    def _initServer(self, locator, serverConnString):
        """
        Инициализация сервера
        :type serverConnString: str строка подключения для serverFromString
        :return : defer.Deferred
        """
        self.history_line.clean()
        self.serverEndpoint = serverFromString(self.reactor, serverConnString)
        savePort = lambda p: save(self, 'serverPort', p)  # given port
        self.serverFactory = Factory.forProtocol(lambda: AMP(locator=locator))
        return self.serverEndpoint.listen(self.serverFactory).addCallback(savePort)

    def _initClient(self, clientConnString):
        """
        Инициализация клиента
        :type clientConnString: str строка подключения для clientFromString
        :return : defer.Deferred с аргументом self.clientProtocol
        """
        clientEndpoint = clientFromString(self.reactor, clientConnString)
        saveProtocol = lambda p: save(self, 'clientProtocol', p)  # given protocol
        self.clientFactory = ClientFactory.forProtocol(AMP)
        return clientEndpoint.connect(self.clientFactory).addCallback(saveProtocol).addCallback(self.setClientProtocol)

    def setClientProtocol(self, proto):
        self.locator.clientProtocol = proto
        return proto

    def setUpServerFromCfg(self, cfg):
        """
        Установить сервер, который будет слушать порт из cfg
        :param cfg: NetworkApplicationConfig
        :rtype : defer.Deferred
        """
        return self._initServer(self.locator, cfg.serverConnString)

    def setUpServerFromStr(self, serverConnString):
        """
        Установить сервер, который будет слушать порт из cfg
        :param serverConnString: str
        :rtype : defer.Deferred с результатом 'tcp:host=localhost:port={0}' где port = который слушает сервер
        """
        return self._initServer(self.locator, serverConnString) \
            .addCallback(lambda sPort: 'tcp:host=localhost:port={0}'.format(sPort.getHost().port))

    def connectAsClientFromStr(self, clientConnString):
        """
        Подключиться как клиент по заданной строке
        :param clientConnString: str
        :rtype : defer.Deferred с аргументом self.clientProtocol
        """
        return self._initClient(clientConnString)

    def setUpClientFromCfg(self, cfg):
        """
        Установить клиента, который будет подключаться по порту из cfg
        :param cfg: NetworkApplicationConfig
        :rtype : defer.Deferred с аргументом self.clientProtocol
        """
        return self._initClient(cfg.clientConnString)

    def __del__(self):
        self.tearDown()

    def tearDown(self):
        d = defer.succeed(None)
        if self.serverPort is not None:
            d = defer.maybeDeferred(self.serverPort.stopListening)
        if self.clientProtocol:
            self.clientProtocol.transport.loseConnection()
        return d