# coding=utf-8
from twisted.internet import defer
from twisted.protocols.amp import Command, Unicode, Float, Boolean
from exceptions import NoTextAvailableException, PatchIsNotApplicableException

__author__ = 'snowy'


class GetTextCommand(Command):
    response = [('text', Unicode())]
    errors = {NoTextAvailableException: 'Невозможно получить текст'}


class Patch(Unicode):
    pass


class ApplyPatchCommand(Command):
    arguments = [('patch', Patch()), ('timestamp', Float())]
    response = [('succeed', Boolean())]
    default_succeed_response = defer.succeed({'succeed': True})
    no_work_is_done_response = defer.succeed({'succeed': None, 'no_work_is_done': True})  # todo: review no work is done
    errors = {
        PatchIsNotApplicableException: 'Патч не может быть применен',
        UnicodeEncodeError: 'Unicode не поддерживается'  # todo: review unicode
    }
    requiresAnswer = True


