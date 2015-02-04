from twisted.python import log


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
            invoked_later_command = lambda: self.view.insert(edit, _index, _inserted_char)
            return lambda: sublime.set_timeout(invoked_later_command, _index * 200)

        for curried_command in [curry_insert_command_later(i, char) for (i, char) in enumerate(text)]:
            curried_command()


def supervisor(result):
    if init.running:
        views = sublime.active_window().views()
        assert len(views) == 2
        appNames = [init.registry[view.id()].application.name for view in views]
        texts = [view.substr(sublime.Region(0, view.size())) for view in views]

        if set(texts) != 1:
            sublime.error_message("Views diverge, see back log")
            init.running = False
            init.registry.clear()
            for i in range(len(views)):
                log.err('{0} text is: {1}'.format(appNames[i], texts[i]))
    return result

# debugView = None
# ":type debugView: sublime.View"
