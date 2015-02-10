__author__ = 'snowy'


def print_it(arg):
    print arg
    return arg


def save(self, key, value):
    setattr(self, key, value)
    return value