from twisted.python import log
from libs.dmp.diff_match_patch import diff_match_patch


__author__ = 'snowy'
import sublime
import sublime_plugin
import init


class ReplayCommand(sublime_plugin.TextCommand):
    """Insert given text with delay. Somehow simulates human typing."""

    def __init__(self, view):
        super(ReplayCommand, self).__init__(view)

    def run(self, edit, text=''):
        def curry_insert_command_later(_index, _inserted_char):
            invoked_later_command = lambda: self.view.insert(edit, self.view.size(), _inserted_char)
            return lambda: sublime.set_timeout(invoked_later_command, _index * 200)

        for curried_command in [curry_insert_command_later(i, char) for (i, char) in enumerate(text)]:
            curried_command()


class ViewsDivergeException(Exception):
    pass


def supervisor_for_2column_layout(result):
    if 'no_work_is_done' in result:
        return result

    if init.running:
        views = sublime.active_window().views()
        assert len(views) == 2
        dmp = diff_match_patch()
        texts = [view.substr(sublime.Region(0, view.size())) for view in views]
        patches = dmp.patch_make(texts[0], texts[1])

        if patches:
            diff_text = dmp.patch_toText(patches)
            appNames = [init.registry[view.id()].application.name for view in views]
            for i in range(len(views)):
                log.err('Error: {0} text is: {1}'.format(appNames[i], texts[i]))
            raise ViewsDivergeException('Views diverge. The diff between texts is:\n{0}'.format(diff_text))
    return result
