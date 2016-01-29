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

"""Unit Tests for oslo.log formatter"""

import mock

from oslo_context import context
from oslo_log import formatters
from oslotest import base as test_base


def _fake_context():
    ctxt = context.RequestContext(user="user",
                                  tenant="tenant",
                                  project_domain="pdomain",
                                  user_domain="udomain",
                                  overwrite=True)

    return ctxt


class AlternativeRequestContext(object):

    def __init__(self, user=None, tenant=None):
        self.user = user
        self.tenant = tenant

    def to_dict(self):
        return {'user': self.user,
                'tenant': self.tenant}


class FormatterTest(test_base.BaseTestCase):

    def setUp(self):
        super(FormatterTest, self).setUp()

    def test_replace_false_value_exists(self):
        d = {"user": "user1"}
        s = "%(user)s" % formatters._ReplaceFalseValue(d)
        self.assertEqual(d['user'], s)

    def test_replace_false_value_not_exists(self):
        d = {"user": "user1"}
        s = "%(project)s" % formatters._ReplaceFalseValue(d)
        self.assertEqual("-", s)

    def test_dictify_context_empty(self):
        self.assertEqual({}, formatters._dictify_context(None))

    @mock.patch("debtcollector.deprecate")
    def test_dictify_context_with_dict(self, mock_deprecate):
        d = {"user": "user"}
        self.assertEqual(d, formatters._dictify_context(d))
        mock_deprecate.assert_not_called()

    @mock.patch("debtcollector.deprecate")
    def test_dictify_context_with_context(self, mock_deprecate):
        ctxt = _fake_context()
        self.assertEqual(ctxt.get_logging_values(),
                         formatters._dictify_context(ctxt))
        mock_deprecate.assert_not_called()

    @mock.patch("debtcollector.deprecate")
    def test_dictify_context_without_get_logging_values(self, mock_deprecate):
        ctxt = AlternativeRequestContext(user="user", tenant="tenant")
        d = {"user": "user", "tenant": "tenant"}
        self.assertEqual(d, formatters._dictify_context(ctxt))
        mock_deprecate.assert_called_with(
            'The RequestContext.get_logging_values() '
            'method should be defined for logging context specific '
            'information.  The to_dict() method is deprecated '
            'for oslo.log use.', removal_version='5.0.0', version='3.8.0')
