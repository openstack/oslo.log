=======
 Usage
=======

In a Library
============

oslo.log is primarily used for configuring logging in an application,
but it does include helpers that can be useful from libraries.

:func:`~oslo_log.log.getLogger` wraps the function of the same name
from Python's standard library to add a
:class:`~oslo_log.log.KeywordArgumentAdapter`, making it easier to
pass data to the formatters provided by oslo.log and configured by an
application.

In an Application
=================

Applications should use oslo.log's configuration functions to register
logging-related configuration options and configure the root and other
default loggers.

Call :func:`~oslo_log.log.register_options` before parsing command
line options.

Call :func:`~oslo_log.log.set_defaults` before configuring logging.

Call :func:`~oslo_log.log.setup` to configure logging for the
application.
