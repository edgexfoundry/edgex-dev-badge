# Copyright (c) 2020 Intel Corporation

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#      http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from mock import patch
from mock import mock_open
from mock import call
from mock import Mock

from badger import Trigger


class TestTrigger(unittest.TestCase):

    def tearDown(self):
        pass

    def test__init__Should_initialize_properly(self, *patches):
        t = Trigger(**dict(merged_pr=1))
        self.assertEqual(t.merged_pr, 1)
        self.assertEqual(t.labels, [])
