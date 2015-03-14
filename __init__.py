# coding=utf-8
"""
Плагин collaboration для совместной работы над файлами. Позволяет редактировать файлы совместно в стиле google-docs.
"""
__author__ = 'snowy'
import os
import sys

# noinspection PyUnboundLocalVariable
__file__ = os.path.normpath(os.path.abspath(__file__))
__path__ = os.path.dirname(__file__)
libs_path = os.path.join(__path__, 'libs')
twisted_path = os.path.join(__path__, 'libs', 'twisted')
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)
if twisted_path not in sys.path:
    sys.path.insert(0, twisted_path)


import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)d - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
logging.getLogger('main').setLevel(logging.DEBUG)
logging.getLogger('core').setLevel(logging.DEBUG)
# from twisted.python import log
# observer = log.PythonLoggingObserver()
# observer.start()
# logger.info('Twisted observer started')