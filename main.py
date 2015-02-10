# coding=utf-8
"""
Модуль отвечающий за основную функциональность приложения. Является sublime специфичной.
Является логической оберткой над core модулем.
"""

__author__ = 'snowy'

import sublime
from core.core import *


class ViewAwareApplication(Application):
    def __init__(self, _reactor, view, name=''):
        super(ViewAwareApplication, self).__init__(_reactor, name)
        self.view = view
        ':type view: sublime.View'
        self.locator = ViewAwareAlgorithm(self.history_line, self.view, self, clientProtocol=self.clientProtocol,
                                          name=name)


class NotThatTypeOfCommandError(Exception):
    pass


class ViewIsReadOnlyException(Exception):
    pass


class ViewAwareAlgorithm(DiffMatchPatchAlgorithm):
    def __init__(self, history_line, view, ownerApplication, initialText='', clientProtocol=None, name=''):
        """
        Алгоритм, который знает о том, что работает с sublime.View
        :param history_line: history.HistoryLine
        :param view: sublime.View
        :param initialText: str
        :param clientProtocol:
        :param name: str
        """
        super(ViewAwareAlgorithm, self).__init__(history_line, initialText=initialText, clientProtocol=clientProtocol,
                                                 name=name)
        self.view = view
        ':type view: sublime.View'
        self.dmp.view = view
        self.ownerApplication = ownerApplication
        ":type ownerApplication: ViewAwareApplication"

    @ApplyPatchCommand.responder
    def remote_applyPatch(self, patch, timestamp):
        if self.view.is_read_only():
            raise ViewIsReadOnlyException("View(id={0}) is read only. Cannot be modified".format(self.view.id()))

        delta_ = timestamp - (time.time() + self.global_delta)
        if delta_ > 0:
            log.msg('ViewAwareAlgorithm: delta_={0}'.format(delta_), logLevel=logging.DEBUG)
            self.ownerApplication.global_delta = delta_ * 1.001

        edit = self.view.begin_edit()
        try:
            log.msg('{0}: <before.view>{1}</before.view>'.format(self.name,
                                                                 self.view.substr(sublime.Region(0, self.view.size()))),
                    logLevel=logging.DEBUG)
            respond = super(ViewAwareAlgorithm, self).remote_applyPatch(patch, timestamp)
            for sublime_command in self.dmp.sublime_patch_commands:
                self.process_sublime_command(edit, sublime_command)
            return respond
        finally:
            self.view.end_edit(edit)
            log.msg('{0}: <after.view>{1}</after.view>'.format(self.name,
                                                               self.view.substr(sublime.Region(0, self.view.size()))),
                    logLevel=logging.DEBUG)

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

            print ('replace({0},{1})'.format(region.a, region.b), self.view.substr(region), '--->', insertion_text)
            self.view.replace(edit, region, insertion_text)

        elif command_type == 'erase':
            assert len(command) < 4
            region = sublime.Region(sublime_start, sublime_stop)
            print ('erase({0},{1})'.format(region.a, region.b), '--->', self.view.substr(region))
            self.view.erase(edit, region)

        else:
            raise NotThatTypeOfCommandError()
