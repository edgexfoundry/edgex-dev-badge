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
