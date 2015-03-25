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

.. _usage-app:

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

General Logging Guidelines
==========================

The `OpenStack Logging Guidelines`_ in openstack-specs repository
explain how to use different logging levels, and the desired logging
patterns to be used in OpenStack applications.

.. _OpenStack Logging Guidelines: http://specs.openstack.org/openstack/openstack-specs/specs/log-guidelines.html

Migrating to oslo.log
=====================

Applications using the incubated version of the logging code from Oslo
may need to make some extra changes.

What do I import?
-----------------

Our goal is to allow most libraries to import the Python standard
library module, ``logging``, and not require ``oslo.log``
directly. Applications may do the same, but if an application takes
advantage of features like passing keywords through to the context for
logging, it is likely to be less confusing to use ``oslo.log``
everywhere, rather than have different types of loggers in different
modules of the application.

No more ``audit()``
-------------------

The ``audit()`` method of the old ``ContextAdapter`` class no longer
exists. We agreed in the `cross project spec`_ to stop using audit
level anyway, so those calls should be replaced with calls to
``info()``.

.. _cross project spec: http://git.openstack.org/cgit/openstack/openstack-specs/tree/specs/log-guidelines.rst

Deprecation tools moved to ``versionutils``
-------------------------------------------

The :meth:`deprecated` decorator and :class:`DeprecatedConfig` have
moved to :mod:`oslo_log.versionutils`.  Replace ``LOG.deprecated()``
with :mod:`oslo_log.versionutils.report_deprecated_feature`, passing a
local logger object as the first argument so the log message includes
the location information.

No more implicit conversion to unicode/str
------------------------------------------

The old :class:`ContextAdapter` used to convert anything given to it
to a :class:`unicode` object before passing it to lower layers of the
logging code. The new logging configuration uses a formatter instead
of an adapter, so this conversion is no longer possible. All message
format strings therefore need to be passed as unicode objects --
that's strictly :class:`unicode`, not :class:`str`. If a message has
no interpolation for extra parameters, a byte string can be used.

The most common place to encounter this is where :meth:`Logger.exception`
is used by passing an exception object as the first argument.

::

    # Old style
    try:
        do_something()
    except Exception as err:
        LOG.exception(err)

Now, the error should be converted to unicode either by calling
:func:`six.text_type` or by using a unicode formatting string to
provide context. It's even better to replace the redundant message
produced by passing the exception with a useful message.

::

    # New style, preferred approach
    from myapp._i18n import _LE  # see oslo.i18n
    try:
        do_something()
    except Exception as err:
        LOG.exception(_LE(u"do_something couldn't do something"))

    # New style, with exception
    from myapp._i18n import _LE  # see oslo.i18n
    try:
        do_something()
    except Exception as err:
        LOG.exception(_LE(u"do_something couldn't do something: %s"), err)

    # New style, alternate without context
    import six
    try:
        do_something()
    except Exception as err:
        LOG.exception(six.text_type(err))

Failure to do this for exceptions or other objects containing
translatable strings from ``oslo.i18n`` results in an exception when
the :class:`_Message` instance is combined in unsupported ways with
the default formatting string inside the :mod:`logging` module in the
standard library.

Changes to App Initialization
-----------------------------

The logging options are no longer registered on the global
configuration object defined in ``oslo.config``, and need to be
registered explicitly on the configuration object being used by the
application. Do this by calling :func:`~oslo_log.log.register_options`
before parsing command line options.

The same configuration option passed to
:func:`~oslo_log.log.register_options` should also be passed as the
first argument to :func:`~oslo_log.log.setup`.

See :ref:`usage-app` for more details about application setup.

Passing Context
---------------

Applications are expected to be using
:class:`oslo_context.context.RequestContext` as the base class for
their application-specific context classes. The base class manages a
thread-local storage for the "current" context object so that
``oslo.log`` can retrieve it without having the value passed in
explicitly. This ensures that all log messages include the same
context information, such as the request id and user
identification. See the ``oslo.context`` documentation for details of
using the class.
