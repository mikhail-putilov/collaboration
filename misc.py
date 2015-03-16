# coding=utf-8
import logging
import sublime
from twisted.internet import task

__author__ = 'snowy'


class ApplicationSpecificAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '[%s] %s' % (self.extra['name'], msg), kwargs


def erase_view(view):
    edit = view.begin_edit()
    try:
        view.erase(edit, sublime.Region(0, view.size()))
    finally:
        view.end_edit(edit)


def all_text_view(view):
    return view.substr(sublime.Region(0, view.size()))

loading_animation = [
    "[=      ]",
    "[ =     ]",
    "[  =    ]",
    "[   =   ]",
    "[    =  ]",
    "[     = ]",
    "[      =]",
    "[     = ]",
    "[    =  ]",
    "[   =   ]",
    "[  =    ]",
    "[ =     ]",
    "[=      ]"
]
loaded = 0


def loading(format_str, *args):
    global loaded
    loaded += 1
    loaded %= len(loading_animation)
    sublime.status_message(format_str.format(loading_animation[loaded], *args))


def loading_wrapper(long_running_deferred, format_str):
    """
    Пока не получен результат long_running_deferred, показывать loading анимацию
    :param long_running_deferred: defer.Deferred
    :param format_str: loading функция вызывается с этим аргументом
    :return: defer.Deferred с результатом long_running_deferred
    """
    l = task.LoopingCall(lambda: loading(format_str))
    l.start(0.1)

    def _got_result(result):
        l.stop()
        return result

    return long_running_deferred.addCallback(_got_result)