# coding=utf-8
"""
Модуль отвечающий за основную sublime специфичную функциональность приложения (!).
Является логической оберткой над core модулем.
"""
from itertools import takewhile, izip
from twisted.protocols.amp import UnknownRemoteError
from history import TimeMachine
import init
# noinspection PyUnresolvedReferences
import sublime
import logging
# noinspection PyUnresolvedReferences
from misc import ApplicationSpecificAdapter, all_text_view
import misc

logger = logging.getLogger(__name__)

__author__ = 'snowy'

from core.core import *


class SublimeAwareApplication(Application):
    def __init__(self, _reactor, view, name=''):
        """
        Application который знает о существовании view.
        :param _reactor: основной реактор
        :param view: соответствующее представление
        :param name: имя (желательно уникальное в рамках одного пира)
        """
        super(SublimeAwareApplication, self).__init__(_reactor, name)
        self.view = view
        ':type view: sublime.View'
        self.locator = SublimeAwareAlgorithm(self.history_line, self.view, self, clientProtocol=self.clientProtocol,
                                             name=name)

    def init_first_text(self, client_proto):
        d = super(SublimeAwareApplication, self).init_first_text(client_proto)

        def _eb(failure):
            failure.trap(UnknownRemoteError)
            sublime.error_message(
                "Couldn't retrieve initial text from a coordinator due to unknown remote error. Aborting.")
            init.terminate_collaboration(self.view.id())
        d.addErrback(_eb)
        return d

    def _got_first_text_cb(self, response):
        _ret = super(SublimeAwareApplication, self)._got_first_text_cb(response)
        edit = self.view.begin_edit()
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit, 0, response['text'])
        self.view.end_edit(edit)
        return _ret


class NotThatTypeOfCommandError(Exception):
    pass


class ViewIsReadOnlyException(Exception):
    pass


class SublimeAwareAlgorithm(DiffMatchPatchAlgorithm):
    def __init__(self, history_line, view, ownerApplication, initialText='', clientProtocol=None, name=''):
        """
        Алгоритм, который знает о том, что работает с sublime.View
        :param history_line: history.HistoryLine История коммитов. От экземпляра ownerApplication
        :param view: sublime.View соответствующее представление
        :param initialText: str начальный текст
        :param clientProtocol: клиентский протокол, отвечающий за соединение с координатором
        :param name: str имя ownerApplication
        """
        super(SublimeAwareAlgorithm, self).__init__(history_line, initialText=initialText,
                                                    clientProtocol=clientProtocol,
                                                    name=name)
        self.view = view
        ':type view: sublime.View'
        self.dmp.view = view
        self.ownerApplication = ownerApplication
        ":type ownerApplication: SublimeAwareApplication"
        self.logger = ApplicationSpecificAdapter(logger, {'name': self.name})
        self.time_machine = TimeMachine(history_line, self)
        self.recovering = False

    @ApplyPatchCommand.responder
    def remote_applyPatch(self, patch, timestamp):
        """
        Применить патч в любом случае. Если патч подходит не идеально, то выполняется вначале RECOVERY.
        :param patch: force-патч от координатора
        :param timestamp: время патча
        :return: :raise ViewIsReadOnlyException: патч не может быть применен из-за read_only флага. Ситуация корректно
        не обрабатывается
        """
        if self.view.is_read_only():
            raise ViewIsReadOnlyException('View(id={0}) is read only. Cannot be modified'.format(self.view.id()))
        before = misc.all_text_view(self.view)
        respond, commands = super(SublimeAwareAlgorithm, self).remote_applyPatch(patch, timestamp)
        assert before == misc.all_text_view(self.view)
        self.logger.debug('starting view modifications:\n<before.view>%s</before.view>', all_text_view(self.view))
        edit = self.view.begin_edit()
        try:
            for sublime_command in commands:
                self.process_sublime_command(edit, sublime_command)
            return respond
        finally:
            self.view.end_edit(edit)
            self.logger.debug('view modifications are ended:\n<after.view>%s</after.view>', all_text_view(self.view))

    def _unknown_coordinators_error_case(self, failure):
        failure.trap(UnknownRemoteError)
        sublime.error_message("Something wet horribly wrong. Coordinator server had crashed. Abort connection.")
        init.terminate_collaboration(self.view.id())

    def start_recovery(self, patch_objects, timestamp):
        """
        RECOVERY процедура. Откатывает патчи, пытается применить патч patch_objects (так, чтобы он применился идеально)
        :param patch_objects: конфликтный патч от координатора
        :param timestamp: время патча
        :return: команды для sublime, которые изменяют view согласно измененной модели
        """
        self.recovering = True
        rollforward_commands, rollback_commands, d1d3 = super(SublimeAwareAlgorithm, self).start_recovery(patch_objects,
                                                                                                          timestamp)
        self.currentText = d1d3
        self.local_onTextChanged(misc.all_text_view(self.view))
        self.recovering = False
        rollback_commands.extend(rollforward_commands)
        return rollback_commands

    def process_sublime_command(self, edit, command):
        """
        Внести изменения в view
        :param edit: sublime.Edit
        :param command: команды, приготовленные dmp во время патчинга
        :raise NotThatTypeOfCommandError: неверный тип команды
        """
        null_padding_len = self.dmp.sublime_null_padding_len
        assert null_padding_len >= 0

        command_type = command[0]
        sublime_start = command[1]
        sublime_stop = command[2]

        if command_type == 'insert':
            text = command[3]
            real_left_padding = 0
            for char in text[:len(text) / 2]:
                if char in u'\x01\x02\x03\x04':
                    real_left_padding += 1

            real_right_padding = 0
            for char in text[len(text) / 2:]:
                # todo: review, what if this characters would be inserted in original text?
                if char in u'\x01\x02\x03\x04':
                    real_right_padding += 1

            # отрезаем u'\x01\x02\x03\x04' из text
            insertion_text = text[real_left_padding:-real_right_padding] \
                if real_right_padding != 0 else text[real_left_padding:]
            a = sublime_start - null_padding_len + real_left_padding
            b = sublime_stop - null_padding_len - real_right_padding

            def common_prefix_f(b1, b2):
                return [i[0] for i in takewhile(lambda x: len(set(x)) == 1, izip(b1, b2))]

            was = self.view.substr(sublime.Region(a, b))
            common_prefix = common_prefix_f(was, insertion_text)
            region = sublime.Region(a + len(common_prefix), b)
            trimed_insertion = insertion_text[len(common_prefix):]
            if region.a == region.b:
                self.logger.debug(
                    'insert(%d), "%s"--->"%s"', region.a, self.view.substr(region), trimed_insertion)
                self.view.insert(edit, region.a, trimed_insertion)
            else:
                self.logger.debug(
                    'replace(%d,%d), "%s"--->"%s"', region.a, region.b, self.view.substr(region), trimed_insertion)
                self.view.replace(edit, region, trimed_insertion)

        elif command_type == 'erase':
            assert len(command) < 4
            region = sublime.Region(sublime_start, sublime_stop)
            self.logger.debug('erase(%d,%d), "%s"--->""', region.a, region.b, self.view.substr(region))
            self.view.erase(edit, region)

        else:
            raise NotThatTypeOfCommandError()


def run_every_second(view_id):
    """
    Функция, которая сканирует и начинает синхронизацию каждую секунду
    :return: функция, которая сканирует конкретную view
    """

    def closure():
        if view_id == 'coordinator':
            return
        app = init.registry[view_id].application
        if app.algorithm.recovering:
            logger.warning('%s is recovering and cannot be scanned for new changes. This must not happen!', app.name)
            return
        app.algorithm.local_onTextChanged(misc.all_text_view(app.view))

    return closure