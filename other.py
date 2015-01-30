from __future__ import print_function
import threading
from time import time, sleep


__author__ = 'snowy'
import sublime

import sublime_plugin

stash = []

spin = True
is_recording = False


class ArgumentError(Exception):
    pass


# noinspection PyClassHasNoInit
class ClearStashCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        global stash
        stash = []


# noinspection PyClassHasNoInit
class StartStopRecordCommand(sublime_plugin.TextCommand):
    def run(self, edit, start_or_stop=None):
        global is_recording
        if start_or_stop == 'start':
            is_recording = True
        elif start_or_stop == 'stop':
            is_recording = False
        else:
            raise ArgumentError('allowed_to_record must be "start" or "stop"')


# noinspection PyClassHasNoInit
class RecordActionsListener(sublime_plugin.EventListener):
    def on_modified(self, view):
        global spin
        # spin = not spin
        if spin and is_recording:
            all_text_region = sublime.Region(0, view.size())
            current_text = view.substr(all_text_region)
            append_to_stash(time(), current_text)


def append_to_stash(when, what):
    stash.append((when, what))


def clear():
    global stash
    stash = []


class FileNotFoundError(Exception):
    pass


# noinspection PyShadowingNames
def compute_delay(stash):
    first_what = stash[0][1]
    processed_stash_copy = [(0, first_what)]
    for i, (when, what) in enumerate(stash):
        if i == 0:
            continue
        previous_when = stash[i - 1][0]
        delay = when - previous_when
        processed_stash_copy.append((delay, what))

    return processed_stash_copy


def replace_view_with_what(what, view):
    edit = view.begin_edit()
    try:
        view.erase(edit, sublime.Region(0, view.size()))
        view.insert(edit, 0, what)
    finally:
        view.end_edit(edit)


class ReplayThread(threading.Thread):
    def __init__(self, view):
        super(ReplayThread, self).__init__()
        self.view = view

    def run(self):
        for delay, what in compute_delay(stash):
            sleep(delay)
            sublime.set_timeout(lambda: replace_view_with_what(what, self.view), 0)


# noinspection PyClassHasNoInit
class ReplayCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        sublime.set_timeout(ReplayThread(self.view).start, 10)


# noinspection PyClassHasNoInit
class LoadFromFileCommand(sublime_plugin.TextCommand):
    def run(self, edit, filename=''):
        if not filename:
            clear()
            raise FileNotFoundError()
        with open(filename) as f:
            clear()
            data = f.read()
            split = data.split('|')
            for when, what in zip(split[::2], split[1::2]):
                append_to_stash(float(when), what)


# noinspection PyShadowingNames
def serialize_stash(stash):
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
        serialized = serialize_stash(stash)
        with open(filename, 'w+b') as f:
            _delete_content(f)
            print(serialized, file=f)


def _delete_content(opened_file):
    opened_file.seek(0)
    opened_file.truncate()