# Copyright (c) 2010-2012 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
from asyncio.exceptions import TimeoutError as AsyncioTimeoutError
import errno
import fcntl
import importlib.metadata

import eventlet
import eventlet.asyncio
import eventlet.debug
import eventlet.greenthread
import eventlet.hubs
import eventlet.hubs.asyncio
import eventlet.patcher

# We want the blocking APIs, because we set file descriptors to non-blocking.
os = eventlet.patcher.original("os")
# Used to communicate between real threads:
SimpleQueue = eventlet.patcher.original("queue").SimpleQueue
# Real OS-level threads:
threading = eventlet.patcher.original("threading")


class _BaseMutex:
    """Shared code for different mutex implementations."""

    def __init__(self):
        self.owner = None
        self.recursion_depth = 0

    def acquire(self, blocking=True):
        """Acquire the mutex.

        If called with blocking=False, returns True if the mutex was
        acquired and False if it wasn't. Otherwise, blocks until the mutex
        is acquired and returns True.
        This lock is recursive; the same greenthread may acquire it as many
        times as it wants to, though it must then release it that many times
        too.
        """
        current_greenthread_id = id(eventlet.greenthread.getcurrent())
        if self.owner == current_greenthread_id:
            self.recursion_depth += 1
            return True

        return self._acquire_eventlet(blocking, current_greenthread_id)

    def release(self):
        """Release the mutex."""
        current_greenthread_id = id(eventlet.greenthread.getcurrent())
        if self.owner != current_greenthread_id:
            raise RuntimeError("cannot release un-acquired lock")

        if self.recursion_depth > 0:
            self.recursion_depth -= 1
            return

        self.owner = None
        self._release_eventlet()

    def close(self):
        """Close the mutex.

        This releases its file descriptors.
        You can't use a mutex after it's been closed.
        """
        self.owner = None
        self.recursion_depth = 0


class _ReallyPipeMutex(_BaseMutex):
    """Mutex using a pipe.

    Works across both greenlets and real threads, even at the same time.

    Class code copied from Swift's swift/common/utils.py
    Related eventlet bug: https://github.com/eventlet/eventlet/issues/432
    """
    def __init__(self):
        super().__init__()

        self.rfd, self.wfd = os.pipe()

        # You can't create a pipe in non-blocking mode; you must set it
        # later.
        rflags = fcntl.fcntl(self.rfd, fcntl.F_GETFL)
        fcntl.fcntl(self.rfd, fcntl.F_SETFL, rflags | os.O_NONBLOCK)
        os.write(self.wfd, b'-')  # start unlocked

        # Usually, it's an error to have multiple greenthreads all waiting
        # to read the same file descriptor. It's often a sign of inadequate
        # concurrency control; for example, if you have two greenthreads
        # trying to use the same memcache connection, they'll end up writing
        # interleaved garbage to the socket or stealing part of each others'
        # responses.
        #
        # In this case, we have multiple greenthreads waiting on the same
        # file descriptor by design. This lets greenthreads in real thread A
        # wait with greenthreads in real thread B for the same mutex.
        # Therefore, we must turn off eventlet's multiple-reader detection.
        #
        # It would be better to turn off multiple-reader detection for only
        # our calls to trampoline(), but eventlet does not support that.
        eventlet.debug.hub_prevent_multiple_readers(False)

    def _acquire_eventlet(self, blocking, current_greenthread_id):
        while True:
            try:
                # If there is a byte available, this will read it and remove
                # it from the pipe. If not, this will raise OSError with
                # errno=EAGAIN.
                os.read(self.rfd, 1)
                self.owner = current_greenthread_id
                return True
            except OSError as err:
                if err.errno != errno.EAGAIN:
                    raise

                if not blocking:
                    return False

                # Tell eventlet to suspend the current greenthread until
                # self.rfd becomes readable. This will happen when someone
                # else writes to self.wfd.
                eventlet.hubs.trampoline(self.rfd, read=True)

    def _release_eventlet(self):
        os.write(self.wfd, b'X')

    def close(self):
        """Close the mutex.

        This releases its file descriptors.
        You can't use a mutex after it's been closed.
        """
        if self.wfd is not None:
            os.close(self.wfd)
            self.wfd = None
        if self.rfd is not None:
            os.close(self.rfd)
            self.rfd = None
        super().close()

    def __del__(self):
        # We need this so we don't leak file descriptors. Otherwise, if you
        # call get_logger() and don't explicitly dispose of it by calling
        # logger.logger.handlers[0].lock.close() [1], the pipe file
        # descriptors are leaked.
        #
        # This only really comes up in tests. Service processes tend to call
        # get_logger() once and then hang on to it until they exit, but the
        # test suite calls get_logger() a lot.
        #
        # [1] and that's a completely ridiculous thing to expect callers to
        # do, so nobody does it and that's okay.
        self.close()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()


class _AsyncioMutex(_BaseMutex):
    """Alternative implementation of mutex for eventlet asyncio hub.

    When using the eventlet asyncio hub, multiple file descriptors as readers
    aren't supported.  So instead, we use two levels of locking:

        1. A normal RLock, for locking across OS threads.

        2. An ``asyncio.Lock`` for locking across greenlets within a single OS
           thread (each OS thread running greenlets has its own asyncio loop)
    """
    def __init__(self):
        super().__init__()
        self._asyncio_lock = asyncio.Lock()
        self._threading_lock = threading.RLock()

    async def _asyncio_acquire(self, blocking, current_greenthread_id):
        if blocking:
            timeout = None
        else:
            timeout = 0.000001
        try:
            await asyncio.wait_for(
                self._asyncio_lock.acquire(), timeout=timeout
            )
        except AsyncioTimeoutError:
            return False
        else:
            self.owner = current_greenthread_id
            return True

    def _acquire_eventlet(self, blocking, current_greenthread_id):
        return eventlet.asyncio.spawn_for_awaitable(
            self._asyncio_acquire(blocking, current_greenthread_id)
        ).wait()

    def acquire(self, blocking=True):
        # First, acquire the RLock:
        rlock_acquired = self._threading_lock.acquire(blocking=False)
        if not rlock_acquired and not blocking:
            return False
        # Simulate blocking while allowing other greenlets to run:
        while not rlock_acquired:
            rlock_acquired = self._threading_lock.acquire(blocking=False)
            # The chance of hitting this path is usually quite low (it requires
            # multiple _OS_ threads having a conflict) and sleeping for too
            # short a time leads to very slow results in one of the tests,
            # perhaps due to lots of context switching overhead. So compromise
            # on a short but not too-short sleep.
            eventlet.sleep(0.0001)
        # Then, do the eventlet locking:
        return super().acquire(blocking=blocking)

    # Preserve documentation, without copy/pasting:
    acquire.__doc__ = _BaseMutex.acquire.__doc__

    def _release_eventlet(self):
        self._asyncio_lock.release()

    def release(self):
        """Release the mutex."""
        # We release in reverse order from acquire(), first eventlet and then
        # the RLock:
        super().release()
        self._threading_lock.release()

    def close(self):
        """Close the mutex."""
        del self._asyncio_lock
        del self._threading_lock
        super().close()


_HUB = eventlet.hubs.get_hub()
if isinstance(_HUB, eventlet.hubs.asyncio.Hub):
    major, minor, patch = map(
        int,
        importlib.metadata.version("eventlet").split(".")[:3]
    )
    if (major, minor, patch) < (0, 38, 2):
        raise RuntimeError(
            "eventlet 0.38.2 or later is required when using asyncio hub"
        )
    PipeMutex = _AsyncioMutex
else:
    PipeMutex = _ReallyPipeMutex


def pipe_createLock(self):
    """Replacement for logging.Handler.createLock method."""
    self.lock = PipeMutex()
