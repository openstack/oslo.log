..
  This work is licensed under a Creative Commons Attribution 3.0 Unported
  License.

  http://creativecommons.org/licenses/by/3.0/legalcode

==================
Logging Guidelines
==================

.. note::

  Many of these guidelines were originally authored as `a cross-project spec
  <https://specs.openstack.org/openstack/openstack-specs/specs/log-guidelines.html>`_.


Motivation
==========

A consistent, unified logging format will better enable cloud
administrators to monitor and maintain their environments.  Therefore
this document provides guidelines for best practices regarding how
developers should use logging within their code.


Adding Variables to Log Messages
================================

String interpolation should be delayed to be handled by the logging
code, rather than being done at the point of the logging call.  For
example, **do not do this**::

  # WRONG
  LOG.info('some message: variable=%s' % variable)

Instead, use this style::

  # RIGHT
  LOG.info('some message: variable=%s', variable)

This allows the logging package to skip creating the formatted log
message if the message is not going to be emitted because of the
current log level.


Definition of Log Levels
========================

.. note::

  The following definitions were originally taken from `a popular
  answer on StackOverflow <http://stackoverflow.com/a/2031209>`_.

``DEBUG``
  Shows everything and is likely not suitable for normal production
  operation due to the sheer size of logs generated.

``INFO``
  Usually indicates successful service start/stop, versions and such
  non-error related data.  This should include largely positive units
  of work that are accomplished (such as starting a compute service,
  creating a user, deleting a volume, etc.).

``AUDIT``
  This should not be used.  All previous messages at ``AUDIT`` level
  should be changed to ``INFO``, or sent as notifications to a
  notification queue.  (The origin of ``AUDIT`` was a NASA-specific
  requirement which led to confusion/misuse and is no longer relevant
  to the current code.)

``WARNING``
  Indicates that there might be a systemic issue; potential
  predictive failure notice.

``ERROR``
  An error has occurred and an administrator should research
  the event.

``CRITICAL``
  An error has occurred and the system might be unstable;
  administrator attention is required immediately.

Log levels from an operator perspective
---------------------------------------

We can think of this from an operator perspective the following ways
(Note: we are not specifying operator policy here, just trying to set
tone for developers that aren't familiar with how these messages will
be interpreted):

``CRITICAL``
  ZOMG!  Cluster on FIRE!  Call all pagers, wake up everyone.  This is
  an unrecoverable error with a service that has or probably will lead
  to service death or massive degradation.

``ERROR``
  Serious issue with cloud: administrator should be notified
  immediately via email/pager.  On call people expected to respond.

``WARNING``
  Something is not right; should get looked into during the next work
  week.  Administrators should be working through eliminating warnings
  as part of normal work.

``INFO``
  Normal status messages showing measurable units of positive work
  passing through under normal functioning of the system.  Should not
  be so verbose as to overwhelm real signal with noise.  Should not be
  continuous "I'm alive!" messages.  See `Log messages at INFO and
  above should represent a "unit of work"`_ for more details.

``DEBUG``
  Developer logging level.  Only enable if you are interested in
  reading through a ton of additional information about what is going
  on.  See `Debugging start / end messages`_ for more details.

``TRACE``
  In functions which support this level, details every parameter and
  operation to help diagnose subtle bugs.  This should only be enabled
  for specific areas of interest or the log volume will be
  overwhelming.  Some system performance degradation should be
  expected.


Overall logging principles
==========================

The following principles should apply to all messages.

Debugging start / end messages
------------------------------

At the ``DEBUG`` log level it is often extremely important to flag the
beginning and ending of actions to track the progression of flows
(which might error out before the unit of work is completed).

This should be made clear by there being a "starting" message with
some indication of completion for that starting point.

In a real OpenStack environment lots of things are happening in
parallel.  There are multiple workers per services, multiple instances
of services in the cloud.

Log messages at INFO and above should represent a "unit of work"
----------------------------------------------------------------

The ``INFO`` log level is defined as: "normal status messages showing
measurable units of positive work passing through under normal
functioning of the system."

A measurable unit of work should be describable by a short sentence
fragment, in the past tense with a noun and a verb of something
significant.

Examples::

  Instance spawned

  Instance destroyed

  Volume attached

  Image failed to copy

Words like "started", "finished", or any verb ending in "ing" are
flags for non unit of work messages.

Examples of good and bad uses of INFO
-------------------------------------

Below are some examples of good and bad uses of ``INFO``.  In the good
examples we can see the 'noun / verb' fragment for a unit of work.
"Successfully" is probably superfluous and could be removed.

**Good**

::

   2014-01-26 15:36:10.597 28297 INFO nova.virt.libvirt.driver [-]
   [instance: b1b8e5c7-12f0-4092-84f6-297fe7642070] Instance spawned
   successfully.

   2014-01-26 15:36:14.307 28297 INFO nova.virt.libvirt.driver [-]
   [instance: b1b8e5c7-12f0-4092-84f6-297fe7642070] Instance destroyed
   successfully.

In the bad examples we see trace-level thinking put into messages at
``INFO`` level and above:

**Bad**

::

   2014-01-26 15:36:11.198 INFO nova.virt.libvirt.driver
   [req-ded67509-1e5d-4fb2-a0e2-92932bba9271
   FixedIPsNegativeTestXml-1426989627 FixedIPsNegativeTestXml-38506689]
   [instance: fd027464-6e15-4f5d-8b1f-c389bdb8772a] Creating image

   2014-01-26 15:36:11.525 INFO nova.virt.libvirt.driver
   [req-ded67509-1e5d-4fb2-a0e2-92932bba9271
   FixedIPsNegativeTestXml-1426989627 FixedIPsNegativeTestXml-38506689]
   [instance: fd027464-6e15-4f5d-8b1f-c389bdb8772a] Using config drive

   2014-01-26 15:36:12.326 AUDIT nova.compute.manager
   [req-714315e2-6318-4005-8f8f-05d7796ff45d FixedIPsTestXml-911165017
   FixedIPsTestXml-1315774890] [instance:
   b1b8e5c7-12f0-4092-84f6-297fe7642070] Terminating instance

   2014-01-26 15:36:12.570 INFO nova.virt.libvirt.driver
   [req-ded67509-1e5d-4fb2-a0e2-92932bba9271
   FixedIPsNegativeTestXml-1426989627 FixedIPsNegativeTestXml-38506689]
   [instance: fd027464-6e15-4f5d-8b1f-c389bdb8772a] Creating config
   drive at
   /opt/stack/data/nova/instances/fd027464-6e15-4f5d-8b1f
   -c389bdb8772a/disk.config

This is mostly an overshare issue.  At ``INFO``, these are stages that
don't really need to be fully communicated.

Messages shouldn't need a secret decoder ring
---------------------------------------------

**Bad**

::

   2014-01-26 15:36:14.256 28297 INFO nova.compute.manager [-]
   Lifecycle event 1 on VM b1b8e5c7-12f0-4092-84f6-297fe7642070

As a general rule, when using constants or enums, ensure they are
translated back to user strings prior to being sent to the user.

Specific event types
--------------------

In addition to the above guidelines very specific additional
recommendations exist.  These are guidelines rather than hard rules to
be adhered to, so common sense should always be exercised.

WSGI requests
~~~~~~~~~~~~~

- Should be logged at ``INFO`` level.

- Should be logged exactly once per request.

- Should include enough information to know what the request was
  (but not so much as to overwhelm the logs).

The last point is notable, because some ``POST`` API requests don't
include enough information in the URL alone to determine what the
API did.  For instance, Nova server actions (where ``POST`` includes a
method name), although including ``POST`` request payloads could be
excessive, so common sense should be exercised.

**Rationale:** Operators should be able to easily see what API
requests their users are making in their cloud to understand the usage
patterns of their users with their cloud.

Operator deprecation warnings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Should be logged at ``WARN`` level.

- Where possible, should be logged exactly once per service start (not
  on every request through code).  However it may be tricky to keep
  track of whether a warning was already issued, so common sense should
  dictate the best approach.

- Should include directions on what to do to migrate from the
  deprecated state.

**Rationale:** Operators need to know that some aspect of their cloud
configuration is now deprecated, and will require changes in the
future.  And they need enough of a bread crumb trail to figure out how
to do that.

REST API deprecation warnings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Should **not** be logged any higher than ``DEBUG``, since these are
  not operator-facing messages.

- Should be logged no more than once per REST API usage / project,
  definitely not on *every* REST API call.

**Rationale:** The users of the REST API don't have access to the
system logs.  Therefore logging at a ``WARNING`` level is telling the
wrong people about the fact that they are using a deprecated API.

Deprecation of user-facing APIs should be communicated via user-facing
mechanisms, e.g. API change notes associated with new API versions.

Stacktraces in logs
~~~~~~~~~~~~~~~~~~~

- Should be **exceptional** events, for unforeseeable circumstances
  that are not yet recoverable by the system.

- Should be logged at ``ERROR`` level.

- Should be considered high priority bugs to be addressed by the
  development team.

**Rationale:** The current behavior of OpenStack is extremely stack
trace happy.  Many existing stack traces in the logs are considered
*normal*.  This dramatically increases the time to find the root cause
of real issues in OpenStack.


Logging by non-OpenStack components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

OpenStack uses a ton of libraries, which have their own definitions of
logging.  This causes a lot of extraneous information in normal logs by
wildly different definitions of those libraries.

As such, all 3rd party libraries should have their logging levels
adjusted so only real errors are logged.

Currently proposed settings for 3rd party libraries:

- ``amqp=WARN``
- ``boto=WARN``
- ``sqlalchemy=WARN``
- ``suds=INFO``
- ``iso8601=WARN``
- ``requests.packages.urllib3.connectionpool=WARN``
- ``urllib3.connectionpool=WARN``


Testing
=======

See tests provided by
https://blueprints.launchpad.net/nova/+spec/clean-logs


References
==========

- Security Log Guidelines -
  https://wiki.openstack.org/wiki/Security/Guidelines/logging_guidelines
- Wiki page for basic logging standards proposal developed early in
  Icehouse - https://wiki.openstack.org/wiki/LoggingStandards
- Apache Log4j levels (which many tools work with) -
  https://logging.apache.org/log4j/1.2/apidocs/org/apache/log4j/Level.html
