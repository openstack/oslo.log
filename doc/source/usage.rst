=======
 Usage
=======

.. _usage-app:

In an Application
=================

When using `Python's standard logging library`_ the following minimal setup
demostrates basic logging.

.. _Python's standard logging library: https://docs.python.org/2/library/logging.html

.. literalinclude:: examples/python_logging.py
   :linenos:
   :lines: 17-26

Source: :download:`examples/python_logging.py`

When using ``Oslo Logging`` the following setup demonstrates a comparative
syntax with Python standard logging.


.. literalinclude:: examples/oslo_logging.py
   :linenos:
   :lines: 17-30
   :emphasize-lines: 8,9

Source: :download:`examples/oslo_logging.py`

Olso Logging Methods
--------------------

Applications need to use the oslo.log configuration functions to register
logging-related configuration options and configure the root and other
default loggers before using standard logging functions.

Call :func:`~oslo_log.log.register_options` with an oslo.config CONF object
before parsing the application command line options.

Optionally call :func:`~oslo_log.log.set_defaults` before setup to
change default logging levels if necessary.

Call :func:`~oslo_log.log.setup` with the oslo.config CONF object used
when registering objects, along with the domain and optionally a version
to configure logging for the application.

Use standard logging functions to produce log records at applicable log
levels.  Logging should also use Oslo i18n contextual functions to provide
translation.  With the use of Oslo Context, log records can also contain
additional contextual information.

Examples
--------


:download:`examples/usage.py` provides a documented example of
Oslo Logging setup.

:download:`examples/usage_helper.py` provides an example showing
debugging logging at each step details the configuration and logging
at each step of Oslo Logging setup.

:download:`examples/usage_i18n.py` provides a documented example of
Oslo Logging with Oslo i18n supported messages.


General Logging Guidelines
==========================

The `OpenStack Logging Guidelines`_ in openstack-specs repository
explain how to use different logging levels, and the desired logging
patterns to be used in OpenStack applications.

.. _OpenStack Logging Guidelines: http://specs.openstack.org/openstack/openstack-specs/specs/log-guidelines.html

In a Library
============

oslo.log is primarily used for configuring logging in an application,
but it does include helpers that can be useful from libraries.

:func:`~oslo_log.log.getLogger` wraps the function of the same name
from Python's standard library to add a
:class:`~oslo_log.log.KeywordArgumentAdapter`, making it easier to
pass data to the formatters provided by oslo.log and configured by an
application.
