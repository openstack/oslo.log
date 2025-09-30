# Copyright 2016 Red Hat, Inc. All Rights Reserved.
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

import collections.abc
import logging
from time import monotonic as monotonic_clock
from typing import Any


class _LogRateLimit(logging.Filter):
    burst: float
    interval: float
    except_level: int | None
    logger: logging.Logger
    counter: int
    end_time: float
    emit_warn: bool

    def __init__(
        self,
        burst: float,
        interval: float,
        except_level: int | None = None,
    ) -> None:
        logging.Filter.__init__(self)
        self.burst = burst
        self.interval = interval
        self.except_level = except_level
        self.logger = logging.getLogger()
        self._reset()

    def _reset(self, now: float | None = None) -> None:
        if now is None:
            now = monotonic_clock()
        self.counter = 0
        self.end_time = now + self.interval
        self.emit_warn = False

    def filter(self, record: logging.LogRecord) -> bool:
        if (
            self.except_level is not None
            and record.levelno >= self.except_level
        ):
            # don't limit levels >= except_level
            return True

        timestamp = monotonic_clock()
        if timestamp >= self.end_time:
            self._reset(timestamp)
            self.counter += 1
            return True

        self.counter += 1
        if self.counter <= self.burst:
            return True
        if self.emit_warn:
            # Allow to log our own warning: self.logger is also filtered by
            # rate limiting
            return True

        if self.counter == self.burst + 1:
            self.emit_warn = True
            self.logger.error(
                "Logging rate limit: drop after %s records/%s sec",
                self.burst,
                self.interval,
            )
            self.emit_warn = False

        # Drop the log
        return False


def _iter_loggers() -> collections.abc.Iterator[logging.Logger]:
    """Iterate on existing loggers."""

    # Sadly, Logger.manager and Manager.loggerDict are not documented,
    # but there is no logging public function to iterate on all loggers.

    # The root logger is not part of loggerDict.
    yield logging.getLogger()

    manager = logging.Logger.manager
    for logger in manager.loggerDict.values():
        if isinstance(logger, logging.PlaceHolder):
            continue
        yield logger


_LOG_LEVELS = {
    'CRITICAL': logging.CRITICAL,
    'ERROR': logging.ERROR,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'DEBUG': logging.DEBUG,
}

# Module-level state for the rate limit filter
_log_filter: _LogRateLimit | None = None
_logger_class: type[logging.Logger] | None = None


def install_filter(
    burst: float, interval: float, except_level: str = 'CRITICAL'
) -> None:
    """Install a rate limit filter on existing and future loggers.

    Limit logs to *burst* messages every *interval* seconds, except of levels
    >= *except_level*. *except_level* is a log level name like 'CRITICAL'. If
    *except_level* is an empty string, all levels are filtered.

    The filter uses a monotonic clock, the timestamp of log records is not
    used.

    Raise an exception if a rate limit filter is already installed.
    """
    global _log_filter, _logger_class

    if _log_filter is not None:
        raise RuntimeError("rate limit filter already installed")

    try:
        except_levelno = _LOG_LEVELS[except_level]
    except KeyError:
        raise ValueError(f"invalid log level name: {except_level!r}")

    log_filter = _LogRateLimit(burst, interval, except_levelno)

    _log_filter = log_filter
    _logger_class = logging.getLoggerClass()

    class RateLimitLogger(_logger_class):  # type: ignore[misc,valid-type]
        def __init__(self, *args: Any, **kw: Any) -> None:
            logging.Logger.__init__(self, *args, **kw)
            self.addFilter(log_filter)

    # Setup our own logger class to automatically add the filter
    # to new loggers.
    logging.setLoggerClass(RateLimitLogger)

    # Add the filter to all existing loggers
    for logger in _iter_loggers():
        logger.addFilter(log_filter)


def uninstall_filter() -> None:
    """Uninstall the rate filter installed by install_filter().

    Do nothing if the filter was already uninstalled.
    """
    global _log_filter, _logger_class

    if _log_filter is None:
        # not installed (or already uninstalled)
        return

    # Restore the old logger class
    if _logger_class is not None:
        logging.setLoggerClass(_logger_class)

    # Remove the filter from all existing loggers
    for logger in _iter_loggers():
        logger.removeFilter(_log_filter)

    _logger_class = None
    _log_filter = None
