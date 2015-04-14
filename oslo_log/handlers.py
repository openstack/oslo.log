#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import inspect
import logging
import logging.config
import logging.handlers
import os


try:
    NullHandler = logging.NullHandler
except AttributeError:  # NOTE(jkoelker) NullHandler added in Python 2.7
    class NullHandler(logging.Handler):
        def handle(self, record):
            pass

        def emit(self, record):
            pass

        def createLock(self):
            self.lock = None


def _get_binary_name():
    return os.path.basename(inspect.stack()[-1][1])


class RFCSysLogHandler(logging.handlers.SysLogHandler):
    def __init__(self, *args, **kwargs):
        self.binary_name = _get_binary_name()
        # Do not use super() unless type(logging.handlers.SysLogHandler)
        #  is 'type' (Python 2.7).
        # Use old style calls, if the type is 'classobj' (Python 2.6)
        logging.handlers.SysLogHandler.__init__(self, *args, **kwargs)

    def format(self, record):
        # Do not use super() unless type(logging.handlers.SysLogHandler)
        #  is 'type' (Python 2.7).
        # Use old style calls, if the type is 'classobj' (Python 2.6)
        msg = logging.handlers.SysLogHandler.format(self, record)
        msg = self.binary_name + ' ' + msg
        return msg

_AUDIT = logging.INFO + 1


class ColorHandler(logging.StreamHandler):
    LEVEL_COLORS = {
        logging.DEBUG: '\033[00;32m',  # GREEN
        logging.INFO: '\033[00;36m',  # CYAN
        _AUDIT: '\033[01;36m',  # BOLD CYAN
        logging.WARN: '\033[01;33m',  # BOLD YELLOW
        logging.ERROR: '\033[01;31m',  # BOLD RED
        logging.CRITICAL: '\033[01;31m',  # BOLD RED
    }

    def format(self, record):
        record.color = self.LEVEL_COLORS[record.levelno]
        return logging.StreamHandler.format(self, record)
