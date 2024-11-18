import os

if os.environ.get("OSLO_LOG_TEST_EVENTLET") == "1":
    import eventlet
    eventlet.monkey_patch()
