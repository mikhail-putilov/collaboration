# coding=utf-8
"""
Основная функциональность. Инкапсулировано от sublime.
Вся бизнес-работа выполняется на основе diff_match_patch объекта.
"""
__author__ = 'snowy'
import logging

from twisted.protocols.amp import CommandLocator, AMP, UnknownRemoteError
from twisted.internet import defer
from twisted.internet.endpoints import serverFromString, clientFromString
from twisted.internet.protocol import Factory, ClientFactory, ServerFactory

import libs.beacon as beacon
from misc import ApplicationSpecificAdapter
import history
from command import *
from exceptions import *
from other import *
from libs.dmp import diff_match_patch


logger = logging.getLogger(__name__)


class CannotConnectToNTPServerException(Exception):
    pass


class DiffMatchPatchAlgorithm(CommandLocator):
    def __init__(self, history_line, initialText='', clientProtocol=None, name=''):
        """
        Основной локатор-алгоритм, действующий только с моделью текста
        :type name: имя владельца (application) (необходимо для логирования)
        :type clientProtocol: клиентский протокол общения с координатором
        :type initialText: str Начальный текст
        :type history_line: history.HistoryLine
        """
        self.name = name
        self.clientProtocol = clientProtocol
        self.currentText = initialText
        self.dmp = diff_match_patch()
        self.history = history_line
        self.time_machine = history.TimeMachine(history_line, self)
        self.logger = ApplicationSpecificAdapter(logger, {'name': name})

    @property
    def local_text(self):
        return self.currentText

    @local_text.setter
    def local_text(self, text):
        """
        Заменить текущий текст без сайд-эффектов
        :param text: str
        """
        self.logger.debug('text is currently replaced without any side-effects')
        self.currentText = text

    def local_onTextChanged(self, nextText):
        """
        Установить текст, посчитать дельту, отправить всем участникам сети патч
        :rtype : defer.Deferred с результатом команды ApplyPatchCommand
        :param nextText: str текст, который является более новой версией текущего текста self.currentText
        """
        # add if recovery running then none
        if self.clientProtocol is None:
            self.logger.debug('client protocol is None')
            return ApplyPatchCommand.no_work_is_done_response

        patches = self.dmp.patch_make(self.currentText, nextText)
        if not patches:
            return ApplyPatchCommand.no_work_is_done_response
        timestamp = self.time_machine.get_current_timestamp()
        self._prepare_and_commit_on_local_changes(patches, nextText, timestamp)
        self.currentText = nextText
        serialized = self.dmp.patch_toText(patches)
        if not serialized:
            return ApplyPatchCommand.no_work_is_done_response
        self.logger.debug('sending patch:\n<patch>\n%s</patch>', serialized)

        def _patch_rejected_case(failure):
            failure.trap(PatchIsNotApplicableException)
            self.logger.warning(str(failure))
            return {'succeed': False}

        return self.clientProtocol.callRemote(TryApplyPatchCommand, patch=serialized, timestamp=timestamp) \
            .addErrback(_patch_rejected_case).addErrback(self._unknown_coordinators_error_case)

    def _unknown_coordinators_error_case(self, failure):
        self.logger.error("Got unknown coordinators error:{0}", str(failure))

    def _prepare_and_commit_on_remote_apply(self, patch_objects, patchedText, timestamp):
        forward = history.HistoryEntry(patch=patch_objects,
                                       timestamp=timestamp,
                                       is_owner=False)
        backward = history.HistoryEntry(patch=self.dmp.patch_make(patchedText, self.currentText),
                                        timestamp=timestamp,
                                        is_owner=False)
        self.history.commit_with_rollback(forward, backward)

    def remote_applyPatch(self, patch, timestamp):
        """
        Применить патч в любом случае. Если патч подходит не идеально, то выполняется вначале RECOVERY.
        :param patch: force-патч от координатора
        :param timestamp: время патча
        :rtype tuple of (response dict, sublime_commands)
        """
        self.logger.debug('remote patch applying:\n<patch>\n%s</patch>', patch)
        # serialize and try to patch
        patch_objects = self.dmp.patch_fromText(patch)
        patchedText, result, commands = self.dmp.patch_apply(patch_objects, self.currentText)
        if False in result:
            # if failed then recovery
            commands = self.start_recovery(patch_objects, timestamp)
            return {'succeed': True}, commands

        before_text = self.currentText
        self._prepare_and_commit_on_remote_apply(patch_objects, patchedText, timestamp)
        self.currentText = patchedText
        self.log_model_text(before_text)

        return {'succeed': True}, commands

    @GetTextCommand.responder
    def remote_getText(self):
        if self.local_text is None:
            raise NoTextAvailableException()
        return {'text': self.local_text}

    def log_failed_apply_patch(self, patch):
        self.logger.debug('remote patch is not applied:\n<patch>\n%s</patch>', patch)

    def _prepare_and_commit_on_local_changes(self, patches, nextText, timestamp):
        forward = history.HistoryEntry(patch=patches,
                                       timestamp=timestamp,
                                       is_owner=True)
        backward = history.HistoryEntry(patch=self.dmp.patch_make(nextText, self.currentText),
                                        timestamp=timestamp,
                                        is_owner=True)
        self.history.commit_with_rollback(forward, backward)
        return

    def log_model_text(self, before_text):
        self.logger.debug('\n<before.model>%s</before.model>\n<after.model>%s</after.model>', before_text,
                          self.currentText)

    def start_recovery(self, patch_objects, timestamp):
        self.log_failed_apply_patch('\n'.join([str(patch) for patch in patch_objects]))
        ret = self.time_machine.start_recovery(patch_objects, timestamp)
        return ret


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
        self.history_line = history.HistoryLine(self)
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
        self.clientFactory = ClientFactory.forProtocol(lambda: AMP(locator=self.locator))
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
        return self._initClient(clientConnString).addCallback(self.init_first_text)

    def _got_first_text_cb(self, response):
        self.algorithm.local_text = response['text']
        return response

    def init_first_text(self, client_proto):
        return client_proto.callRemote(GetTextCommand).addCallback(self._got_first_text_cb) \
            .addCallback(lambda ignore: client_proto)  # make sure that result value is still client_proto

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


class TryApplyPatchCommand(Command):
    arguments = [('patch', Patch()), ('timestamp', Float())]
    response = [('succeed', Boolean())]
    errors = {
        PatchIsNotApplicableException: 'Патч не может быть применен. '
                                       'Сделайте пул, зарезолвите конфликты, потом сделайте пуш',
        UnicodeEncodeError: 'Unicode не поддерживается'  # todo: review unicode
    }


class CoordinatorLocatorDecorator(CommandLocator):
    def __init__(self, to_be_decorated_locator):
        """
        Координатор. Лишает права конфликтовать
        :param to_be_decorated_locator: DiffMatchPatchAlgorithm
        """
        assert isinstance(to_be_decorated_locator,
                          DiffMatchPatchAlgorithm), 'current version of locator must be DiffMatchPatchAlgorithm'
        self.peers = []
        self.decorated_locator = to_be_decorated_locator
        # self.main_locator должен строго относиться к нарушению контекста патча.
        # Поэтому необходимо включить set_perfect_matching
        self.set_perfect_matching()
        self.logger = ApplicationSpecificAdapter(logger, {'name': self.decorated_locator.name})

    @GetTextCommand.responder
    def get_text(self):
        return self.decorated_locator.remote_getText()

    @TryApplyPatchCommand.responder
    def try_apply_patch(self, patch, timestamp):
        # если applyPatch не пройдет, то будет вызвано исключение и
        # вызывающий пир будет уведомлен о PatchIsNotApplicableException
        self.decorated_locator.remote_applyPatch(patch, timestamp)
        # все остальные пиры должны принять изменения, даже если это противоречит их религии
        # force push
        for peer in self.peers:
            peer.callRemote(ApplyPatchCommand, patch=patch, timestamp=timestamp)
        return {'succeed': True}

    def add_incoming_connection(self, server_proto):
        assert hasattr(server_proto, 'callRemote'), 'clientProtocol должен иметь метод callRemote ' \
                                                    'для того, чтобы можно было отправлять AMP пакеты'
        self.peers.append(server_proto)

    def clean_incoming_connections(self):
        del self.peers
        self.peers = []

    def remove_incoming_connection(self, server_proto):
        assert hasattr(server_proto, 'callRemote'), 'server_proto должен иметь метод callRemote ' \
                                                    'для того, чтобы можно было отправлять AMP пакеты'
        self.peers.remove(server_proto)

    def set_perfect_matching(self):
        self.decorated_locator.dmp.Match_Threshold = 0.0


class CoordinatorDiffMatchPatchAlgorithm(DiffMatchPatchAlgorithm):
    def start_recovery(self, patch_objects, timestamp):
        raise PatchIsNotApplicableException('Your following patch is rejected:\n<patch>\n{0}</patch>'.format(
            ''.join([str(patch) for patch in patch_objects])))


class CoordinatorApplication(Application):
    def __init__(self, reactor, name='Coordinator', initial_text=''):
        super(CoordinatorApplication, self).__init__(reactor, name=name)
        self.server_ports = []
        self.decorated_locators = []
        self.beacon = beacon.Beacon(12000, "collaboration-sublime-text")
        self.beacon.daemon = True
        self.locator = CoordinatorDiffMatchPatchAlgorithm(self.history_line, clientProtocol=self.clientProtocol,
                                                          name=name, initialText=initial_text)

    def _start_beacon(self):
        self.beacon.start()

    def _initServer(self, locator, serverConnString):
        """
        Инициализация сервера с многими подключениями
        :type serverConnString: str строка подключения для serverFromString
        :return : defer.Deferred
        """
        self._start_beacon()
        self.history_line.clean()
        for decorated_locator in self.decorated_locators:
            decorated_locator.clean_incoming_connections()
        self.serverEndpoint = serverFromString(self.reactor, serverConnString)
        self.serverFactory = MultipleConnectionServerFactory(locator)

        def connected_cb(port):
            self.server_ports.append(port)
            return port

        return self.serverEndpoint.listen(self.serverFactory).addCallback(connected_cb)

    def tearDown(self):
        assert self.clientProtocol is None, 'Coordinator is not a client for any peer'
        del self.beacon
        d = defer.succeed(None)
        if self.server_ports:
            d = defer.DeferredList([defer.maybeDeferred(serverPort.stopListening) for serverPort in self.server_ports])
        return d


class MultipleConnectionServerFactory(ServerFactory):
    def __init__(self, coordinator_locator):
        """
        Фабрика по созданию протоколов на каджый входящий запрос. У всех локаторов созданных
        протоколов один и тот же предок - coordinator_locator
        :param coordinator_locator: DiffMatchPatchAlgorithm основной локатор, который выполняет всю нагрузку по патчингу
        """
        self.coordinator_locator = coordinator_locator
        # протокол AMP с локатором CoordinatorLocatorDecorator
        self.protocol = lambda: AMP(locator=CoordinatorLocatorDecorator(coordinator_locator))
        self.already_proto = []
        ":type already_proto: list [AMP]"

    def buildProtocol(self, addr):
        proto = Factory.buildProtocol(self, addr)
        for prev_proto in self.already_proto:
            assert isinstance(prev_proto.locator, CoordinatorLocatorDecorator), 'Каждый локатор должен быть ' \
                                                                                'декорирован для задания своего ' \
                                                                                'списка incoming_connections'
            assert prev_proto.locator.decorated_locator is self.coordinator_locator, 'координирующий ' \
                                                                                     'локатор должен быть один'
            prev_proto.locator.add_incoming_connection(proto)
            proto.locator.add_incoming_connection(prev_proto)

        # add for the next protos
        self.already_proto.append(proto)
        return proto
