# coding=utf-8
from twisted.internet import defer
from twisted.protocols.amp import Command, Unicode, Float, Boolean
from exceptions import NoTextAvailableException, PatchIsNotApplicableException, PatchIsNotApplicableException

__author__ = 'snowy'


class GetTextCommand(Command):
    response = [('text', Unicode())]
    errors = {NoTextAvailableException: 'Невозможно получить текст'}


class Patch(Unicode):
    pass


class ApplyPatchCommand(Command):
    arguments = [('patch', Patch()), ('timestamp', Float())]
    requiresAnswer = False


class TryApplyPatchCommand(Command):
    arguments = [('patch', Patch()), ('timestamp', Float())]
    response = [('succeed', Boolean())]
    errors = {
        PatchIsNotApplicableException: 'Патч не может быть применен. '
                                       'Сделайте пул, зарезолвите конфликты, потом сделайте пуш'
    }