# Copyright (c) 2016 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""A usage example of Oslo Logging with context

This example requires the following package to be installed.

$ pip install oslo.log

Additional Oslo packages installed include oslo.config, oslo.context,
oslo.i18n, oslo.serialization and oslo.utils.

More information about Oslo Logging can be found at:

  https://docs.openstack.org/oslo.log/latest/user/index.html
  https://docs.openstack.org/oslo.context/latest/user/index.html
"""

from oslo_config import cfg
from oslo_context import context
from oslo_log import log as logging

LOG = logging.getLogger(__name__)
CONF = cfg.CONF
DOMAIN = 'demo'


def prepare():
    """Prepare Oslo Logging (2 or 3 steps)

    Use of Oslo Logging involves the following:

    * logging.register_options
    * logging.set_defaults (optional)
    * logging.setup
    """

    # Required step to register common, logging and generic configuration
    # variables
    logging.register_options(CONF)

    # Optional step to set new defaults if necessary for
    # * logging_context_format_string
    # * default_log_levels
    #
    # These variables default to respectively:
    #
    #  import oslo_log
    #  oslo_log._options.DEFAULT_LOG_LEVELS
    #  oslo_log._options.log_opts[0].default
    #

    extra_log_level_defaults = [
        'dogpile=INFO',
        'routes=INFO'
        ]

    logging.set_defaults(
        default_log_levels=logging.get_default_log_levels() +
        extra_log_level_defaults)

    # Required setup based on configuration and domain
    logging.setup(CONF, DOMAIN)


if __name__ == '__main__':
    prepare()

    LOG.info("Welcome to Oslo Logging")
    LOG.info("Without context")
    context.RequestContext(user='6ce90b4d',
                           project='d6134462',
                           domain='a6b9360e')
    LOG.info("With context")
