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

from __future__ import print_function

import argparse
import collections
import functools
import sys

from oslo_serialization import jsonutils
from oslo_utils import importutils
import six

termcolor = importutils.try_import('termcolor')

from oslo_log import log


_USE_COLOR = False


def main():
    global _USE_COLOR
    args = parse_args()
    _USE_COLOR = args.color
    formatter = functools.partial(console_format, args.prefix, args.locator)
    for line in reformat_json(args.file, formatter):
        print(line)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("file",
                        nargs='?', default=sys.stdin,
                        type=argparse.FileType(),
                        help="JSON log file to read from (if not provided"
                             " standard input is used instead)")
    parser.add_argument("--prefix",
                        default='%(asctime)s.%(msecs)03d'
                                ' %(process)s %(levelname)s %(name)s',
                        help="Message prefixes")
    parser.add_argument("--locator",
                        default='[%(funcname)s %(pathname)s:%(lineno)s]',
                        help="Locator to append to DEBUG records")
    parser.add_argument("-c", "--color",
                        action='store_true', default=False,
                        help="Color log levels (requires `termcolor`)")
    args = parser.parse_args()
    if args.color and not termcolor:
        raise ImportError("Coloring requested but `termcolor` is not"
                          " importable")
    return args


def colorise(key, text=None):
    if text is None:
        text = key
    if not _USE_COLOR:
        return text
    colors = {
        'exc': ('red', ['reverse', 'bold']),
        'FATAL': ('red', ['reverse', 'bold']),
        'ERROR': ('red', ['bold']),
        'WARNING': ('yellow', ['bold']),
        'WARN': ('yellow', ['bold']),
        'INFO': ('white', ['bold']),
    }
    color, attrs = colors.get(key, ('', []))
    if color:
        return termcolor.colored(text, color=color, attrs=attrs)
    return text


def warn(prefix, msg):
    return "%s: %s" % (colorise('exc', prefix), msg)


def reformat_json(fh, formatter):
    # using readline allows interactive stdin to respond to every line
    while True:
        line = fh.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            record = jsonutils.loads(line)
        except ValueError:
            yield warn("Not JSON", line)
            continue
        for out_line in formatter(record):
            yield out_line


def console_format(prefix, locator, record):
    # Provide an empty string to format-specifiers the record is
    # missing, instead of failing. Doesn't work for non-string
    # specifiers.
    record = collections.defaultdict(str, record)
    levelname = record.get('levelname')
    if levelname:
        record['levelname'] = colorise(levelname)

    try:
        prefix = prefix % record
    except TypeError:
        # Thrown when a non-string format-specifier can't be filled in.
        # Dict comprehension cleans up the output
        yield warn('Missing non-string placeholder in record',
                   {str(k): str(v) if isinstance(v, six.string_types) else v
                    for k, v in six.iteritems(record)})
        return

    locator = ''
    if (record.get('levelno', 100) <= log.DEBUG or levelname == 'DEBUG'):
        locator = locator % record

    yield ' '.join(x for x in [prefix, record['message'], locator] if x)

    tb = record.get('traceback')
    if tb:
        for tb_line in tb.splitlines():
            yield ' '.join([prefix, tb_line])


if __name__ == '__main__':
    main()
