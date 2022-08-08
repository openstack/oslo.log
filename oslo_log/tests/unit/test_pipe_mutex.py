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

import contextlib
import unittest
from unittest import mock

import eventlet
from eventlet import debug as eventlet_debug
from eventlet import greenpool

from oslo_log import pipe_mutex


@contextlib.contextmanager
def quiet_eventlet_exceptions():
    orig_state = greenpool.DEBUG
    eventlet_debug.hub_exceptions(False)
    try:
        yield
    finally:
        eventlet_debug.hub_exceptions(orig_state)


class TestPipeMutex(unittest.TestCase):
    """From  Swift's test/unit/common/test_utils.py"""
    def setUp(self):
        self.mutex = pipe_mutex.PipeMutex()

    def tearDown(self):
        self.mutex.close()

    def test_nonblocking(self):
        evt_lock1 = eventlet.event.Event()
        evt_lock2 = eventlet.event.Event()
        evt_unlock = eventlet.event.Event()

        def get_the_lock():
            self.mutex.acquire()
            evt_lock1.send('got the lock')
            evt_lock2.wait()
            self.mutex.release()
            evt_unlock.send('released the lock')

        eventlet.spawn(get_the_lock)
        evt_lock1.wait()  # Now, the other greenthread has the lock.

        self.assertFalse(self.mutex.acquire(blocking=False))
        evt_lock2.send('please release the lock')
        evt_unlock.wait()  # The other greenthread has released the lock.
        self.assertTrue(self.mutex.acquire(blocking=False))

    def test_recursive(self):
        self.assertTrue(self.mutex.acquire(blocking=False))
        self.assertTrue(self.mutex.acquire(blocking=False))

        def try_acquire_lock():
            return self.mutex.acquire(blocking=False)

        self.assertFalse(eventlet.spawn(try_acquire_lock).wait())
        self.mutex.release()
        self.assertFalse(eventlet.spawn(try_acquire_lock).wait())
        self.mutex.release()
        self.assertTrue(eventlet.spawn(try_acquire_lock).wait())

    def test_release_without_acquire(self):
        self.assertRaises(RuntimeError, self.mutex.release)

    def test_too_many_releases(self):
        self.mutex.acquire()
        self.mutex.release()
        self.assertRaises(RuntimeError, self.mutex.release)

    def test_wrong_releaser(self):
        self.mutex.acquire()
        with quiet_eventlet_exceptions():
            self.assertRaises(RuntimeError,
                              eventlet.spawn(self.mutex.release).wait)

    def test_blocking(self):
        evt = eventlet.event.Event()

        sequence = []

        def coro1():
            eventlet.sleep(0)  # let coro2 go

            self.mutex.acquire()
            sequence.append('coro1 acquire')
            evt.send('go')
            self.mutex.release()
            sequence.append('coro1 release')

        def coro2():
            evt.wait()  # wait for coro1 to start us
            self.mutex.acquire()
            sequence.append('coro2 acquire')
            self.mutex.release()
            sequence.append('coro2 release')

        c1 = eventlet.spawn(coro1)
        c2 = eventlet.spawn(coro2)

        c1.wait()
        c2.wait()

        self.assertEqual(sequence, [
            'coro1 acquire',
            'coro1 release',
            'coro2 acquire',
            'coro2 release'])

    def test_blocking_tpool(self):
        # Note: this test's success isn't a guarantee that the mutex is
        # working. However, this test's failure means that the mutex is
        # definitely broken.
        sequence = []

        def do_stuff():
            n = 10
            while n > 0:
                self.mutex.acquire()
                sequence.append("<")
                eventlet.sleep(0.0001)
                sequence.append(">")
                self.mutex.release()
                n -= 1

        greenthread1 = eventlet.spawn(do_stuff)
        greenthread2 = eventlet.spawn(do_stuff)

        real_thread1 = eventlet.patcher.original('threading').Thread(
            target=do_stuff)
        real_thread1.start()

        real_thread2 = eventlet.patcher.original('threading').Thread(
            target=do_stuff)
        real_thread2.start()

        greenthread1.wait()
        greenthread2.wait()
        real_thread1.join()
        real_thread2.join()

        self.assertEqual(''.join(sequence), "<>" * 40)

    def test_blocking_preserves_ownership(self):
        pthread1_event = eventlet.patcher.original('threading').Event()
        pthread2_event1 = eventlet.patcher.original('threading').Event()
        pthread2_event2 = eventlet.patcher.original('threading').Event()
        thread_id = []
        owner = []

        def pthread1():
            thread_id.append(id(eventlet.greenthread.getcurrent()))
            self.mutex.acquire()
            owner.append(self.mutex.owner)
            pthread2_event1.set()

            orig_os_write = pipe_mutex.os.write

            def patched_os_write(*a, **kw):
                try:
                    return orig_os_write(*a, **kw)
                finally:
                    pthread1_event.wait()

            with mock.patch.object(pipe_mutex.os, 'write', patched_os_write):
                self.mutex.release()
            pthread2_event2.set()

        def pthread2():
            pthread2_event1.wait()  # ensure pthread1 acquires lock first
            thread_id.append(id(eventlet.greenthread.getcurrent()))
            self.mutex.acquire()
            pthread1_event.set()
            pthread2_event2.wait()
            owner.append(self.mutex.owner)
            self.mutex.release()

        real_thread1 = eventlet.patcher.original('threading').Thread(
            target=pthread1)
        real_thread1.start()

        real_thread2 = eventlet.patcher.original('threading').Thread(
            target=pthread2)
        real_thread2.start()

        real_thread1.join()
        real_thread2.join()
        self.assertEqual(thread_id, owner)
        self.assertIsNone(self.mutex.owner)

    @classmethod
    def tearDownClass(cls):
        # PipeMutex turns this off when you instantiate one
        eventlet.debug.hub_prevent_multiple_readers(True)
