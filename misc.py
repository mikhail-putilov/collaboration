import logging
import sublime

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

loading_anim = [
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


def loading():
    global loaded
    loaded += 1
    loaded %= len(loading_anim)
    sublime.status_message(loading_anim[loaded])