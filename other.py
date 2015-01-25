from __future__ import print_function
from time import time, sleep


__author__ = 'snowy'
import sublime

import sublime_plugin

stash = []

spin = True
allowed_to_record = False


class ArgumentError(Exception):
    pass


# noinspection PyClassHasNoInit
class StartStopRecordCommand(sublime_plugin.TextCommand):
    def run(self, edit, start_or_stop=None):
        global allowed_to_record
        if start_or_stop == 'start':
            allowed_to_record = True
        elif start_or_stop == 'stop':
            allowed_to_record = False
        else:
            raise ArgumentError('allowed_to_record must be "start" or "stop"')


# noinspection PyClassHasNoInit
class RecordActionsListener(sublime_plugin.EventListener):
    def on_modified(self, view):
        global spin
        spin = not spin
        if spin and allowed_to_record:
            all_text_region = sublime.Region(0, view.size())
            current_text = view.substr(all_text_region)
            save(time(), current_text)


def save(when, what):
    stash.append((when, what))


def clear():
    global stash
    stash = []


class FileNotFoundError(Exception):
    pass


# noinspection PyShadowingNames
def compute_delay(stash):
    first_what = stash[0][1]
    res = [(0, first_what)]
    for i, (when, what) in enumerate(stash):
        if i == 0:
            continue
        previous_when = stash[i - 1][0]
        delay = when - previous_when
        res.append((delay, what))

    return res


# noinspection PyClassHasNoInit
class ReplayCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        for delay, what in compute_delay(stash):
            sleep(0.4)
            edit = self.view.begin_edit()
            try:
                self.view.erase(edit, sublime.Region(0, self.view.size()))
                self.view.insert(edit, 0, what)
            finally:
                self.view.end_edit(edit)


# noinspection PyClassHasNoInit
class LoadFromFileCommand(sublime_plugin.TextCommand):
    def run(self, edit, filename=''):
        clear()
        if not filename:
            raise FileNotFoundError()
        with open(filename) as f:
            data = f.read()
            split = data.split('|')
            for when, what in zip(split[::2], split[1::2]):
                save(float(when), what)


def serialize_stash():
    serialized = ''
    for entry in stash:
        when, what = entry
        serialized += '|' + str(when) + '|' + what
    return serialized[1:]


# noinspection PyClassHasNoInit
class SaveToFileCommand(sublime_plugin.TextCommand):
    def run(self, edit, filename=''):
        if not filename:
            raise FileNotFoundError()
        serialized = serialize_stash()
        with open(filename, 'w+b') as f:
            print(serialized, file=f)