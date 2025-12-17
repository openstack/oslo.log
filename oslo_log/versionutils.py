# Copyright (c) 2013 OpenStack Foundation
# All Rights Reserved.
#
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

"""
Helpers for comparing version strings.
"""

import functools
import inspect
import logging
from typing import Any, TypeVar, cast, overload
from collections.abc import Callable

from oslo_config import cfg

from oslo_log._i18n import _


_F = TypeVar('_F', bound=Callable[..., Any])
_C = TypeVar('_C', bound=type[Any])

LOG = logging.getLogger(__name__)
CONF = cfg.CONF
_DEPRECATED_EXCEPTIONS = set()


deprecated_opts = [
    cfg.BoolOpt(
        'fatal_deprecations',
        default=False,
        help='Enables or disables fatal status of deprecations.',
    ),
]


_deprecated_msg_with_alternative = _(
    '%(what)s is deprecated as of %(as_of)s in favor of '
    '%(in_favor_of)s and may be removed in %(remove_in)s.'
)

_deprecated_msg_no_alternative = _(
    '%(what)s is deprecated as of %(as_of)s and may be '
    'removed in %(remove_in)s. It will not be superseded.'
)

_deprecated_msg_with_alternative_no_removal = _(
    '%(what)s is deprecated as of %(as_of)s in favor of %(in_favor_of)s.'
)

_deprecated_msg_with_no_alternative_no_removal = _(
    '%(what)s is deprecated as of %(as_of)s. It will not be superseded.'
)


_RELEASES = {
    'F': 'Folsom',
    'G': 'Grizzly',
    'H': 'Havana',
    'I': 'Icehouse',
    'J': 'Juno',
    'K': 'Kilo',
    'L': 'Liberty',
    'M': 'Mitaka',
    'N': 'Newton',
    'O': 'Ocata',
    'P': 'Pike',
    'Q': 'Queens',
    'R': 'Rocky',
    'S': 'Stein',
    'T': 'Train',
    'U': 'Ussuri',
    'V': 'Victoria',
    'W': 'Wallaby',
    'X': 'Xena',
    'Y': 'Yoga',
    'Z': 'Zed',
    '2023.1': '2023.1',
    '2023.2': '2023.2',
    '2024.1': '2024.1',
    '2024.2': '2024.2',
    '2025.1': '2025.1',
    '2025.2': '2025.2',
    '2026.1': '2026.1',
    '2026.2': '2026.2',
    '2027.1': '2027.1',
    '2027.2': '2027.2',
    '2028.1': '2028.1',
    '2028.2': '2028.2',
}

_RELEASE_KEYS = list(_RELEASES)


def register_options() -> None:
    """Register configuration options used by this library.

    .. note: This is optional since the options are also registered
        automatically when the functions in this module are used.

    """
    CONF.register_opts(deprecated_opts)


class deprecated:
    """A decorator to mark callables as deprecated.

    This decorator logs a deprecation message when the callable it decorates is
    used. The message will include the release where the callable was
    deprecated, the release where it may be removed and possibly an optional
    replacement. It also logs a message when a deprecated exception is being
    caught in a try-except block, but not when subclasses of that exception
    are being caught.

    Examples:

    1. Specifying the required deprecated release

    >>> @deprecated(as_of=deprecated.ICEHOUSE)
    ... def a():
    ...     pass

    2. Specifying a replacement:

    >>> @deprecated(as_of=deprecated.ICEHOUSE, in_favor_of='f()')
    ... def b():
    ...     pass

    3. Specifying the release where the functionality may be removed:

    >>> @deprecated(as_of=deprecated.ICEHOUSE, remove_in=+1)
    ... def c():
    ...     pass

    4. Specifying the deprecated functionality will not be removed:

    >>> @deprecated(as_of=deprecated.ICEHOUSE, remove_in=None)
    ... def d():
    ...     pass

    5. Specifying a replacement, deprecated functionality will not be removed:

    >>> @deprecated(
    ...     as_of=deprecated.ICEHOUSE, in_favor_of='f()', remove_in=None
    ... )
    ... def e():
    ...     pass

    .. warning::

       The hook used to detect when a deprecated exception is being
       *caught* does not work under Python 3. Deprecated exceptions
       are still logged if they are thrown.

    """

    FOLSOM = 'F'
    GRIZZLY = 'G'
    HAVANA = 'H'
    ICEHOUSE = 'I'
    JUNO = 'J'
    KILO = 'K'
    LIBERTY = 'L'
    MITAKA = 'M'
    NEWTON = 'N'
    OCATA = 'O'
    PIKE = 'P'
    QUEENS = 'Q'
    ROCKY = 'R'
    STEIN = 'S'
    TRAIN = 'T'
    USSURI = 'U'
    VICTORIA = 'V'
    WALLABY = 'W'
    XENA = 'X'
    YOGA = 'Y'
    ZED = 'Z'
    ANTELOPE = '2023.1'
    BOBCAT = '2023.2'
    CARACAL = '2024.1'
    DALMATIAN = '2024.2'
    EPOXY = '2025.1'
    FLAMINGO = '2026.1'
    GAZPACHO = '2026.2'

    def __init__(
        self,
        as_of: str,
        in_favor_of: str | None = None,
        remove_in: int | None = 2,
        what: str | None = None,
    ) -> None:
        """Initialize decorator

        :param as_of: the release deprecating the callable. Constants
            are define in this class for convenience.
        :param in_favor_of: the replacement for the callable (optional)
        :param remove_in: an integer specifying how many releases to wait
            before removing (default: 2)
        :param what: name of the thing being deprecated (default: the
            callable's name)

        """
        self.as_of = as_of
        self.in_favor_of = in_favor_of
        self.remove_in = remove_in
        self.what = what

    @overload
    def __call__(self, func_or_cls: _C) -> _C: ...

    @overload
    def __call__(self, func_or_cls: _F) -> _F: ...

    def __call__(self, func_or_cls: _F | _C) -> _F | _C:
        report_deprecated = functools.partial(
            deprecation_warning,
            what=self.what or func_or_cls.__name__ + '()',
            as_of=self.as_of,
            in_favor_of=self.in_favor_of,
            remove_in=self.remove_in,
        )

        if inspect.isfunction(func_or_cls):

            @functools.wraps(func_or_cls)
            def wrapped(*args: Any, **kwargs: Any) -> Any:
                report_deprecated()
                return func_or_cls(*args, **kwargs)

            return cast(_F, wrapped)
        elif inspect.isclass(func_or_cls):
            orig_init = func_or_cls.__init__

            @functools.wraps(orig_init, assigned=('__name__', '__doc__'))
            def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
                if self.__class__ in _DEPRECATED_EXCEPTIONS:
                    report_deprecated()
                orig_init(self, *args, **kwargs)

            func_or_cls.__init__ = new_init
            _DEPRECATED_EXCEPTIONS.add(func_or_cls)

            if issubclass(func_or_cls, Exception):
                # NOTE(dhellmann): The subclasscheck is called,
                # sometimes, to test whether a class matches the type
                # being caught in an exception. This lets us warn
                # folks that they are trying to catch an exception
                # that has been deprecated. However, under Python 3
                # the test for whether one class is a subclass of
                # another has been optimized so that the abstract
                # check is only invoked in some cases. (See
                # PyObject_IsSubclass in cpython/Objects/abstract.c
                # for the short-cut.)
                class ExceptionMeta(type):
                    def __subclasscheck__(self, subclass: type) -> bool:
                        if self in _DEPRECATED_EXCEPTIONS:
                            report_deprecated()
                        return super().__subclasscheck__(subclass)

                func_or_cls.__meta__ = ExceptionMeta
                _DEPRECATED_EXCEPTIONS.add(func_or_cls)

            return cast(_C, func_or_cls)
        else:
            raise TypeError(
                'deprecated can be used only with functions or classes'
            )


def _get_safe_to_remove_release(release: str, remove_in: int | None) -> str:
    if remove_in is None:
        remove_in = 0

    new_release_idx = _RELEASE_KEYS.index(release) + remove_in
    try:
        return _RELEASES[_RELEASE_KEYS[new_release_idx]]
    except IndexError:
        return 'UNKOWN'


def deprecation_warning(
    what: str,
    as_of: str,
    in_favor_of: str | None = None,
    remove_in: int | None = 2,
    logger: logging.Logger = LOG,
) -> None:
    """Warn about the deprecation of a feature.

    :param what: name of the thing being deprecated.
    :param as_of: the release deprecating the callable.
    :param in_favor_of: the replacement for the callable (optional)
    :param remove_in: an integer specifying how many releases to wait
        before removing (default: 2)
    :param logger: the logging object to use for reporting (optional).
    """
    details = dict(
        what=what,
        as_of=_RELEASES[as_of],
        remove_in=_get_safe_to_remove_release(as_of, remove_in),
    )

    if in_favor_of:
        details['in_favor_of'] = in_favor_of
        if remove_in is not None and remove_in > 0:
            msg = _deprecated_msg_with_alternative
        else:
            # There are no plans to remove this function, but it is
            # now deprecated.
            msg = _deprecated_msg_with_alternative_no_removal
    else:
        if remove_in is not None and remove_in > 0:
            msg = _deprecated_msg_no_alternative
        else:
            # There are no plans to remove this function, but it is
            # now deprecated.
            msg = _deprecated_msg_with_no_alternative_no_removal

    report_deprecated_feature(logger, msg, details)


# Track the messages we have sent already. See
# report_deprecated_feature().
_deprecated_messages_sent: dict[str, list[Any]] = {}


def report_deprecated_feature(
    logger: logging.Logger,
    msg: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Call this function when a deprecated feature is used.

    If the system is configured for fatal deprecations then the message
    is logged at the 'critical' level and :class:`DeprecatedConfig` will
    be raised.

    Otherwise, the message will be logged (once) at the 'warn' level.

    :raises: :class:`DeprecatedConfig` if the system is configured for
             fatal deprecations.
    """
    stdmsg = _("Deprecated: %s") % msg
    register_options()
    if CONF.fatal_deprecations:
        logger.critical(stdmsg, *args, **kwargs)
        raise DeprecatedConfig(msg=stdmsg)

    # Using a list because a tuple with dict can't be stored in a set.
    sent_args = _deprecated_messages_sent.setdefault(msg, list())

    if args in sent_args:
        # Already logged this message, so don't log it again.
        return

    sent_args.append(args)
    logger.warning(stdmsg, *args, **kwargs)


class DeprecatedConfig(Exception):
    message = _("Fatal call to deprecated config: %(msg)s")

    def __init__(self, msg: str) -> None:
        super(Exception, self).__init__(self.message % dict(msg=msg))
