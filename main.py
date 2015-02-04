# coding=utf-8
import other

__author__ = 'snowy'

import sublime_plugin
import sublime

from core.core import *
import init


class ViewAwareApplication(Application):
    def __init__(self, _reactor, view, name=''):
        super(ViewAwareApplication, self).__init__(_reactor, name)
        self.view = view
        ':type view: sublime.View'
        self.locator = ViewAwareAlgorithm(self.view, self, clientProtocol=self.clientProtocol, name=name)


class NotThatTypeOfCommandError(Exception):
    pass


class ViewAwareAlgorithm(DiffMatchPatchAlgorithm):
    def __init__(self, view, ownerApplication, initialText='', clientProtocol=None, name=''):
        """
        Алгоритм, который знает о том, что работает с sublime.View
        :param view: sublime.View
        :param initialText: str
        :param clientProtocol:
        :param name: str
        """
        super(ViewAwareAlgorithm, self).__init__(initialText, clientProtocol, name)
        self.view = view
        ':type view: sublime.View'
        self.dmp.view = view
        self.ownerApplication = ownerApplication
        ":type ownerApplication: ViewAwareApplication"

    def remote_applyPatch(self, patch):
        print "remote!"
        edit = self.view.begin_edit()
        try:
            log.msg('{0}: <before>{1}</before>'.format(self.name, self.currentText),
                    logLevel=logging.DEBUG)
            respond = super(ViewAwareAlgorithm, self).remote_applyPatch(patch)
            for sublime_command in self.dmp.sublime_patch_commands:
                self.process_sublime_command(edit, sublime_command)
            return respond
        finally:
            self.view.end_edit(edit)
            log.msg('{0}: <after>{1}</after>'.format(self.name, self.view.substr(sublime.Region(0, self.view.size()))),
                    logLevel=logging.DEBUG)


    def process_sublime_command(self, edit, command):
        """
        Внести изменения в view
        :param edit: sublime.Edit
        :param command: команды, приготовленные dmp во время патчинга
        :raise NotThatTypeOfCommandError: не верный тип команды
        """
        null_padding_len = self.dmp.sublime_null_padding_len
        assert null_padding_len >= 0

        command_type = command[0]
        sublime_start = command[1]
        sublime_stop = command[2]

        if command_type == 'insert':
            text = command[3]
            delta = 0
            for char in text[:len(text) / 2]:
                if char in u'\x01\x02\x03\x04':
                    delta += 1
            new_start = delta
            delta_end = 0
            for char in text[len(text) / 2:]:
                # todo: review, what if this characters would be inserted in original text?
                if char in u'\x01\x02\x03\x04':
                    delta_end += 1
            new_stop = delta_end

            # отрезаем u'\x01\x02\x03\x04' из text
            insertion_text = text[new_start:-new_stop] if new_stop != 0 else text[new_start:]
            a = sublime_start + new_start - null_padding_len
            b = sublime_stop - (new_start + new_stop)
            region = sublime.Region(a, b)

            print ('insert', region.a, region.b, insertion_text)
            self.view.replace(edit, region, insertion_text)

        elif command_type == 'erase':
            assert command.size() < 4
            region = sublime.Region(sublime_start, sublime_stop)
            print ('erase', region.a, region.b, self.view.substr(region))
            self.view.erase(edit, region)

        else:
            raise NotThatTypeOfCommandError()


# noinspection PyClassHasNoInit
class MainDispatcherListener(sublime_plugin.EventListener):
    def on_modified(self, view):
        """
        Ивент, срабатывает каждый раз при редактировании текста. Запускает всю процедуру патчинга и отправки оповещений
        :param view: sublime.View
        """
        if view.id() in init.registry:
            app = init.registry[view.id()].application
            allTextRegion = sublime.Region(0, view.size())
            allText = view.substr(allTextRegion)
            app.algorithm.local_onTextChanged(allText) \
                .addCallbacks(self.debug, self.log_any_failure_and_errmsg_eb)

    def debug(self, result):
        log.msg('debug!', logLevel=logging.DEBUG)

    # noinspection PyMethodMayBeStatic
    def log_any_failure_and_errmsg_eb(self, failure):
        """
        В случае, если не получается apply patch, то выводим сообщение об ошибке, а не умираем тихо
        :param failure: twisted.python.Failure
        """
        failure.trap(Exception)
        log.err(failure)
        sublime.error_message(str(failure))
