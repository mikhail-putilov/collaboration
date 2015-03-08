# coding=utf-8
"""
Модуль отвечающий за основную функциональность приложения. Является sublime специфичной.
Является логической оберткой над core модулем.
"""
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
        super(SublimeAwareApplication, self).__init__(_reactor, name)
        self.view = view
        ':type view: sublime.View'
        self.locator = SublimeAwareAlgorithm(self.history_line, self.view, self, clientProtocol=self.clientProtocol,
                                             name=name)


class NotThatTypeOfCommandError(Exception):
    pass


class ViewIsReadOnlyException(Exception):
    pass


class SublimeAwareAlgorithm(DiffMatchPatchAlgorithm):
    def __init__(self, history_line, view, ownerApplication, initialText='', clientProtocol=None, name=''):
        """
        Алгоритм, который знает о том, что работает с sublime.View
        :param history_line: history.HistoryLine
        :param view: sublime.View
        :param initialText: str
        :param clientProtocol:
        :param name: str
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
        if self.view.is_read_only():
            raise ViewIsReadOnlyException('View(id={0}) is read only. Cannot be modified'.format(self.view.id()))

        respond, commands = super(SublimeAwareAlgorithm, self).remote_applyPatch(patch, timestamp)
        self.logger.debug('starting view modifications:\n<before.view>%s</before.view>', all_text_view(self.view))
        edit = self.view.begin_edit()
        try:
            for sublime_command in commands:
                self.process_sublime_command(edit, sublime_command)
            return respond
        finally:
            self.view.end_edit(edit)
            self.logger.debug('view modifications are ended:\n<after.view>%s</after.view>', all_text_view(self.view))

    def start_recovery(self, patch_objects, timestamp):
        self.recovering = True
        rollforward_commands, rollback_commands, d1d3 = super(SublimeAwareAlgorithm, self).start_recovery(patch_objects, timestamp)
        edit = self.view.begin_edit()
        try:
            for cmd in rollback_commands:
                self.process_sublime_command(edit, cmd)
            for command in rollforward_commands:
                self.process_sublime_command(edit, command)
        finally:
            self.view.end_edit(edit)
        self.currentText = d1d3
        self.local_onTextChanged(misc.all_text_view(self.view))
        self.recovering = False
        return []

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
            region = sublime.Region(a, b)
            if region.a == region.b:
                self.logger.debug(
                    'insert(%d), "%s"--->"%s"', region.a, self.view.substr(region), insertion_text)
                self.view.insert(edit, region.a, insertion_text)
            else:
                self.logger.debug(
                    'replace(%d,%d), "%s"--->"%s"', region.a, region.b, self.view.substr(region), insertion_text)
                self.view.replace(edit, region, insertion_text)

        elif command_type == 'erase':
            assert len(command) < 4
            region = sublime.Region(sublime_start, sublime_stop)
            self.logger.debug('erase(%d,%d), "%s"--->""', region.a, region.b, self.view.substr(region))
            self.view.erase(edit, region)

        else:
            raise NotThatTypeOfCommandError()


def run_every_second(view_id):
    """Функция, которая запускает синхронизацию между view"""
    def closure():
        if view_id == 'coordinator':
            return
        app = init.registry[view_id].application
        if app.algorithm.recovering:
            logger.warning('%s is recovering and cannot be scanned for new changes. This must not happen!', app.name)
            return
        app.algorithm.local_onTextChanged(misc.all_text_view(app.view))
    return closure