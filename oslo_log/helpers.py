# Copyright (C) 2013 eNovance SAS <licensing@enovance.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Log helper functions."""

import functools
import logging


def _get_full_class_name(cls):
    return '%s.%s' % (cls.__module__,
                      getattr(cls, '__qualname__', cls.__name__))


def log_method_call(method):
    """Decorator helping to log method calls.

    :param method: Method to decorate to be logged.
    :type method: method definition
    """
    log = logging.getLogger(method.__module__)

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        if args:
            first_arg = args[0]
            cls = (first_arg if isinstance(first_arg, type)
                   else first_arg.__class__)
            caller = _get_full_class_name(cls)
        else:
            caller = 'static'
        data = {'caller': caller,
                'method_name': method.__name__,
                'args': args[1:], 'kwargs': kwargs}
        log.debug('%(caller)s method %(method_name)s '
                  'called with arguments %(args)s %(kwargs)s', data)
        return method(*args, **kwargs)
    return wrapper
