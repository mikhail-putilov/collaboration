__author__ = 'snowy'
import sublime
import sublime_plugin


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

# debugView = None
# ":type debugView: sublime.View"
