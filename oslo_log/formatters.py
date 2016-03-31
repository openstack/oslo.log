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

import datetime
import itertools
import logging
import logging.config
import logging.handlers
import socket
import sys
import traceback

from dateutil import tz
import six
from six import moves

from oslo_context import context as context_utils
from oslo_serialization import jsonutils


def _dictify_context(context):
    if context is None:
        return {}
    if not isinstance(context, dict) and getattr(context, 'to_dict', None):
        context = context.to_dict()
    return context


# A configuration object is given to us when the application registers
# the logging options.
_CONF = None


def _store_global_conf(conf):
    global _CONF
    _CONF = conf


def _update_record_with_context(record):
    """Given a log record, update it with context information.

    The request context, if there is one, will either be in the
    extra values for the incoming record or in the global
    thread-local store.
    """
    context = record.__dict__.get(
        'context',
        context_utils.get_current()
    )
    d = _dictify_context(context)
    # Copy the context values directly onto the record so they can be
    # used by the formatting strings.
    for k, v in d.items():
        setattr(record, k, v)
    return context


class _ReplaceFalseValue(dict):
    def __getitem__(self, key):
        return dict.get(self, key, None) or '-'


class JSONFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        # NOTE(jkoelker) we ignore the fmt argument, but its still there
        #                since logging.config.fileConfig passes it.
        self.datefmt = datefmt
        try:
            self.hostname = socket.gethostname()
        except socket.error:
            self.hostname = None

    def formatException(self, ei, strip_newlines=True):
        lines = traceback.format_exception(*ei)
        if strip_newlines:
            lines = [moves.filter(
                lambda x: x,
                line.rstrip().splitlines()) for line in lines]
            lines = list(itertools.chain(*lines))
        return lines

    def format(self, record):
        message = {'message': record.getMessage(),
                   'asctime': self.formatTime(record, self.datefmt),
                   'name': record.name,
                   'msg': record.msg,
                   'args': record.args,
                   'levelname': record.levelname,
                   'levelno': record.levelno,
                   'pathname': record.pathname,
                   'filename': record.filename,
                   'module': record.module,
                   'lineno': record.lineno,
                   'funcname': record.funcName,
                   'created': record.created,
                   'msecs': record.msecs,
                   'relative_created': record.relativeCreated,
                   'thread': record.thread,
                   'thread_name': record.threadName,
                   'process_name': record.processName,
                   'process': record.process,
                   'traceback': None,
                   'hostname': self.hostname}

        # Build the extra values that were given to us, including
        # the context.
        context = _update_record_with_context(record)
        if hasattr(record, 'extra'):
            extra = record.extra.copy()
        else:
            extra = {}
        for key in getattr(record, 'extra_keys', []):
            if key not in extra:
                extra[key] = getattr(record, key)
        # If we saved a context object, explode it into the extra
        # dictionary because the values are more useful than the
        # object reference.
        if 'context' in extra:
            extra.update(_dictify_context(context))
            del extra['context']
        message['extra'] = extra

        if record.exc_info:
            message['traceback'] = self.formatException(record.exc_info)

        return jsonutils.dumps(message)


class ContextFormatter(logging.Formatter):
    """A context.RequestContext aware formatter configured through flags.

    The flags used to set format strings are: logging_context_format_string
    and logging_default_format_string.  You can also specify
    logging_debug_format_suffix to append extra formatting if the log level is
    debug.

    The standard variables available to the formatter are listed at:
    http://docs.python.org/library/logging.html#formatter

    In addition to the standard variables, one custom variable is
    available to both formatting string: `isotime` produces a
    timestamp in ISO8601 format, suitable for producing
    RFC5424-compliant log messages.

    Furthermore, logging_context_format_string has access to all of
    the data in a dict representation of the context.
    """

    def __init__(self, *args, **kwargs):
        """Initialize ContextFormatter instance

        Takes additional keyword arguments which can be used in the message
        format string.

        :keyword project: project name
        :type project: string
        :keyword version: project version
        :type version: string

        """

        self.project = kwargs.pop('project', 'unknown')
        self.version = kwargs.pop('version', 'unknown')
        self.conf = kwargs.pop('config', _CONF)

        logging.Formatter.__init__(self, *args, **kwargs)

    def format(self, record):
        """Uses contextstring if request_id is set, otherwise default."""

        # NOTE(jecarey): If msg is not unicode, coerce it into unicode
        #                before it can get to the python logging and
        #                possibly cause string encoding trouble
        if not isinstance(record.msg, six.text_type):
            record.msg = six.text_type(record.msg)

        # store project info
        record.project = self.project
        record.version = self.version

        # FIXME(dims): We need a better way to pick up the instance
        # or instance_uuid parameters from the kwargs from say
        # LOG.info or LOG.warn
        instance_extra = ''
        instance = getattr(record, 'instance', None)
        instance_uuid = getattr(record, 'instance_uuid', None)
        context = _update_record_with_context(record)
        if instance:
            try:
                instance_extra = (self.conf.instance_format
                                  % instance)
            except TypeError:
                instance_extra = instance
        elif instance_uuid:
            instance_extra = (self.conf.instance_uuid_format
                              % {'uuid': instance_uuid})
        elif context:
            # FIXME(dhellmann): We should replace these nova-isms with
            # more generic handling in the Context class.  See the
            # app-agnostic-logging-parameters blueprint.
            instance = getattr(context, 'instance', None)
            instance_uuid = getattr(context, 'instance_uuid', None)

            # resource_uuid was introduced in oslo_context's
            # RequestContext
            resource_uuid = getattr(context, 'resource_uuid', None)

            if instance:
                instance_extra = (self.conf.instance_format
                                  % {'uuid': instance})
            elif instance_uuid:
                instance_extra = (self.conf.instance_uuid_format
                                  % {'uuid': instance_uuid})
            elif resource_uuid:
                instance_extra = (self.conf.instance_uuid_format
                                  % {'uuid': resource_uuid})

        record.instance = instance_extra

        # NOTE(sdague): default the fancier formatting params
        # to an empty string so we don't throw an exception if
        # they get used
        for key in ('instance', 'color', 'user_identity', 'resource',
                    'user_name', 'project_name'):
            if key not in record.__dict__:
                record.__dict__[key] = ''

        # Set the "user_identity" value of "logging_context_format_string"
        # by using "logging_user_identity_format" and
        # "to_dict()" of oslo.context.
        if context:
            record.user_identity = (
                self.conf.logging_user_identity_format %
                _ReplaceFalseValue(context.__dict__)
            )

        if record.__dict__.get('request_id'):
            fmt = self.conf.logging_context_format_string
        else:
            fmt = self.conf.logging_default_format_string

        if (record.levelno == logging.DEBUG and
                self.conf.logging_debug_format_suffix):
            fmt += " " + self.conf.logging_debug_format_suffix

        self._compute_iso_time(record)

        if sys.version_info < (3, 2):
            self._fmt = fmt
        else:
            self._style = logging.PercentStyle(fmt)
            self._fmt = self._style._fmt
        # Cache this on the record, Logger will respect our formatted copy
        if record.exc_info:
            record.exc_text = self.formatException(record.exc_info, record)
        return logging.Formatter.format(self, record)

    def formatException(self, exc_info, record=None):
        """Format exception output with CONF.logging_exception_prefix."""
        if not record:
            return logging.Formatter.formatException(self, exc_info)

        stringbuffer = moves.StringIO()
        traceback.print_exception(exc_info[0], exc_info[1], exc_info[2],
                                  None, stringbuffer)
        lines = stringbuffer.getvalue().split('\n')
        stringbuffer.close()

        if self.conf.logging_exception_prefix.find('%(asctime)') != -1:
            record.asctime = self.formatTime(record, self.datefmt)

        self._compute_iso_time(record)

        formatted_lines = []
        for line in lines:
            pl = self.conf.logging_exception_prefix % record.__dict__
            fl = '%s%s' % (pl, line)
            formatted_lines.append(fl)
        return '\n'.join(formatted_lines)

    def _compute_iso_time(self, record):
        # set iso8601 timestamp
        localtz = tz.tzlocal()
        record.isotime = datetime.datetime.fromtimestamp(
            record.created).replace(tzinfo=localtz).isoformat()
        if record.created == int(record.created):
            # NOTE(stpierre): when the timestamp includes no
            # microseconds -- e.g., 1450274066.000000 -- then the
            # microseconds aren't included in the isoformat() time. As
            # a result, in literally one in a million cases
            # isoformat() looks different. This adds microseconds when
            # that happens.
            record.isotime = "%s.000000%s" % (record.isotime[:-6],
                                              record.isotime[-6:])
