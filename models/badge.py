import os
import logging
import yaml
import re

from .base import Base
from .trigger import Trigger

logger = logging.getLogger(__name__)

class Badge(Base):
    def __init__(self, **entries):
        super(Badge, self).__init__(**entries)

        trigger_dict = self.trigger
        if trigger_dict is not None:
            self.trigger = Trigger(**trigger_dict)

        # set optional attributes
        if not 'include' in entries:
            self.include = None
        else:
            self.include = re.compile(self.include)

        if not 'exclude' in entries:
            self.exclude = None
        else:
            self.exclude = re.compile(self.exclude)

        if not 'enabled' in entries:
            self.enabled = True

        if not 'begin_on' in entries:
            self.begin_on = None

        if not 'end_on' in entries:
            self.end_on = None

    @staticmethod
    def from_yaml(badge_yaml):
        if 'badges' in badge_yaml:
            return [Badge(**b) for b in badge_yaml['badges']]
        else:
            return []

    def process(self, org, prs_by_repo, persist=False):
        winners = []

        filtered_prs, author_details = self.filter_prs(prs_by_repo)

        if len(filtered_prs) > 0:
            db = self.get_db(org, persist)

            for author in filtered_prs:
                prs = filtered_prs[author]
                pr_count = len(prs)

                # if author == 'ernestojeda':
                #     pr_count = 16

                author_record = self.get_author_record(org, author, db)

                if pr_count >= self.trigger.merged_pr:
                    winner_details = self.get_winner_details(pr_count, prs, author, author_details)

                    logger.debug("========================================")
                    logger.debug(
                        f"  - {author}: [{pr_count}] Needs...[{self.trigger.merged_pr}]")

                    if not author_record:
                        logger.debug(f"Congrats! {author} met the threshold!")
                        if persist:
                            if self.trigger.rolling:
                                self.add_db_record(org, author, pr_count)
                            else:
                                self.add_db_record(org, author)
                        winners.append(winner_details)

                    # this is not a requirement, just nice to have
                    else:
                        logger.debug(
                            f"User [{author}] has already achieved this badge. Lets check if they qualify for a rolling badge")

                        if self.trigger.rolling:
                            last_pr_count = int(author_record[1])

                            if pr_count <= self.trigger.max_rolling_prs:
                                next_tier = self.trigger.get_next_rolling(last_pr_count, pr_count)
                                logger.debug(
                                    "========================================")
                                logger.debug(
                                    f"  - {author}: [{pr_count}] Needs...[{next_tier}]")

                                if last_pr_count != pr_count and pr_count >= next_tier:
                                    logger.debug(
                                        f"Yes, this is a rolling badge! Congrats! {author} met the threshold again!")

                                    if persist:
                                        self.update_db_record(org, author, pr_count)

                                    winners.append(winner_details)
                        else:
                            logger.debug('Not a rolling badge, continue...')
        return winners

    def filter_prs(self, prs_by_repo):
        filtered_prs = {}
        author_details = {}

        for repo_name in prs_by_repo:
            if self.eligible_repo(repo_name):
                logger.debug(f"{repo_name} is eligible!")
                pr_by_user = prs_by_repo[repo_name]

                if pr_by_user:
                    for author in pr_by_user:
                        eligible_prs = self.eligible_prs(pr_by_user[author])

                        if len(eligible_prs) > 0:
                            author_details[author] = f"{eligible_prs[0].author_name}:{eligible_prs[0].author_email}"

                            if author not in filtered_prs:
                                filtered_prs[author] = []
                            filtered_prs[author] += eligible_prs
                else:
                    logger.debug(f"[{self.id}] No eligible PR's found for badges in repo [{repo_name}]")
            else:
                logger.debug(f"{repo_name} not eligible did not meet requirements.")

        return (filtered_prs, author_details)

    def get_db_file(self, org):
        return f"./badges/{org}/{self.id}"

    def get_db(self, org, persist=False):
        path = self.get_db_file(org)

        if os.access(path, os.R_OK):
            with open(path) as f:
                data = f.readlines()
                db = []

                for s in data:
                    record = s.strip().replace('\n', '').split(':')
                    db.append(record)

                return db
        else:
            # create an an empty file, if it doesn't exist yet
            if persist:
                try:
                    os.makedirs(os.path.dirname(path))
                except FileExistsError:
                    pass

                with open(path, 'w') as f:
                    pass
            return []

    def get_winner_details(self, pr_count, prs, author, author_details):
        counted_pr_list = [f"{pr.number} - {pr.repo}/{pr.title}" for pr in prs]
        deets = author_details[author].split(':')
        return dict(
            author=author, name=deets[0], email=deets[1], count=pr_count, counted_prs=counted_pr_list)

    def get_author_record(self, org, author, db=None):
        if db is None:
            db = self.get_db(org)

        author_record = None
        for record in db:
            if record[0] == author:
                author_record = record
                break

        return author_record

    def add_db_record(self, org, author, pr_count=None):
        path = self.get_db_file(org)
        with open(path, 'a') as f:
            if pr_count is None:
                f.write(f"{author}\n")
            else:
                f.write(f"{author}:{pr_count}\n")

    def update_db_record(self, org, author, pr_count):
        db = self.get_db(org)
        new_db = []
        for record in db:
            if record[0] == author:
                new_db.append([author, str(pr_count)])
            else:
                new_db.append(record)

        #only write if nothing changed
        if new_db != db:
            path = self.get_db_file(org)
            with open(path, 'w') as f:
                for record in new_db:
                    f.write(f"{':'.join(record)}\n")

    def eligible_repo(self, repo_name):
        eligible = False

        if self.include is None and self.exclude is None:
            eligible = True
        else:
            if self.include is not None and self.include.match(repo_name):
                # print(f"{repo_name} is eligible. include: {self.include.pattern}")
                eligible = True

            # exclude should always trump include
            if self.exclude is not None and self.exclude.match(repo_name):
                #print(f"{repo_name} is not eligible. exclude: {self.exclude}")
                eligible = False

        return eligible

    def eligible_prs(self, pr_list):
        eligible_prs = []
        for pr in pr_list:
            # if the date looks good, continue
            logger.debug(
                f"Checking PR: {pr.repo} {pr.title} {pr.author} {pr.labels}")
            if self.check_trigger_date(pr) and self.check_trigger_labels(pr):
                logger.debug(f"PR {pr.title} is eligible")
                eligible_prs.append(pr)

        return eligible_prs

    def check_trigger_date(self, pr):
        if self.begin_on is None and self.end_on is None:
            return True
        else:
            in_range = False

            # check if date is between start and end
            if self.begin_on is not None and self.end_on is not None:
                if self.begin_on <= pr.created_at <= self.end_on:
                    in_range = True

            # otherwise if start or end are missing, check those
            else:
                if (self.begin_on is not None and self.end_on is None) and pr.created_at >= self.begin_on:
                    in_range = True
                elif (self.end_on is not None and self.begin_on is None) and pr.created_at <= self.end_on:
                    in_range = True

            return in_range

    def check_trigger_labels(self, pr):
        trigger_label_count = len(self.trigger.labels)
        if trigger_label_count == 0:
            return True
        else:
            match_count = 0
            should_match = trigger_label_count
            for label_regex in self.trigger.labels:
                m = False
                for label in pr.labels:
                    if label_regex.match(label):
                        m = True
                if m:
                    match_count += 1

            # if all the rules match, we good
            if match_count == should_match:
                return True

        return False

