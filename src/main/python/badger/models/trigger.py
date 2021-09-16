# Copyright (c) 2021 Intel Corporation

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#      http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re

from .base import Base

class Trigger(Base):
    def __init__(self, **entries):
        super(Trigger, self).__init__(**entries)

        if not 'labels' in entries:
            self.labels = []

        if not 'rolling' in entries:
            self.rolling = False

        if not 'max' in entries:
            self.max_rolling_prs = 100 * self.merged_pr #can only win 100 times
        else:
            self.max_rolling_prs = self.max * self.merged_pr

        # build regex's
        labels_regex = [re.compile(label) for label in self.labels]
        self.labels = labels_regex

    def get_next_rolling(self, last_pr_count, pr_count):
        if self.rolling:
            tiers = []
            for r in range(self.max_rolling_prs+1):
                if r != 0 and r % self.merged_pr == 0 and r > last_pr_count:
                    tiers.append(r)
            return min(tiers, key=lambda x: abs(x-pr_count))

        return None
