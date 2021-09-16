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

import logging
import json

from datetime import datetime
from progress1bar import ProgressBar
from string import Template

from .api import API
from .base import Base

logger = logging.getLogger(__name__)

QUERIES = {
    'queryRepositories': """
        {
          search(query: "org:$org archived:false", type: REPOSITORY, first: $page_size, after: "$cursor") {
            repositoryCount
            pageInfo {
              endCursor
              hasNextPage
            }
            edges {
              cursor
              node {
                ... on Repository {
                  name
                }
              }
            }
          }
        }
    """,
    'queryPullRequests': """
        {
          search(query: "is:pr is:merged $closed repo:$owner/$repo", type: ISSUE, first: $page_size, after: "$cursor") {
            issueCount
            pageInfo {
              endCursor
              hasNextPage
            }
            edges {
              cursor
              node {
                ... on PullRequest {
                  title
                  number
                  createdAt
                  closedAt
                  labels(first: 10) {
                    nodes {
                      name
                    }
                  }
                  author {
                    ... on User {
                      login
                      email
                      name
                    }
                  }
                }
              }
            }
          }
        }
    """
}

class PullRequest(Base):
    def __init__(self, **entries):
        super(PullRequest, self).__init__(**entries)

        # time to close, datediff
        # might be useful in the future if we want to create
        # tiggers for #of days open
        self.ttc = self.closed_at - self.created_at

    @staticmethod
    def sanitize(query):
        """ sanitize query
        """
        return query.replace('  ', '').replace('\n', ' ')

    @staticmethod
    def get_query(name, **kwargs):
        """ return contributions query
        """
        query = QUERIES[name]

        if not kwargs.get('cursor'):
            query = query.replace(', after: "$cursor"', '')
        if not kwargs.get('closed'):
            query = query.replace(' $closed', '')

        sanitized_query = PullRequest.sanitize(query) # maybe move this to api.py
        query_template = Template(sanitized_query)

        return query_template.substitute(**kwargs)

    @staticmethod
    def get_org_repos(client, org, global_exclude=None):
        """ get repositories
        """
        kwargs = {
            'org': org,
            'page_size': 100,
        }

        cursor = ''
        print(f'Getting repositories for org "{org}"')

        repositories = []
        while True:
            kwargs['cursor'] = cursor
            query = PullRequest.get_query('queryRepositories', **kwargs)
            response = client.graphql(query)

            repos = response['data']['search']['edges']

            for repo in repos:
                repo_name = repo['node']['name']
                if global_exclude is None or not global_exclude.match(repo_name):
                    repositories.append(repo_name)
            has_next_page = response['data']['search']['pageInfo']['hasNextPage']

            if not has_next_page:
                break

            cursor = response['data']['search']['pageInfo']['endCursor']

        return repositories

    @staticmethod
    def get_repo_prs(client, org, repo_name, target=None):
        """ process pull requests
        """

        kwargs = {
            'owner': org,
            'repo': repo_name,
            'page_size': 0,
        }

        if target:
            kwargs['closed'] = f'closed:>{target}'
        
        # query to get total
        query = PullRequest.get_query('queryPullRequests', **kwargs)
        total = client.graphql(query)['data']['search']['issueCount']

        if total == 0:
            print(f'No PRs for {repo_name}')
            return

        completed_message = f'Done processing {str(total).zfill(3)} PRs for'
        with ProgressBar(completed_message=completed_message) as progress_bar:
            progress_bar.alias = repo_name
            progress_bar.total = total

            kwargs['page_size'] = 100
            cursor = ''

            prs_by_author = {}
            while True:
                kwargs['cursor'] = cursor
                query = PullRequest.get_query('queryPullRequests', **kwargs)
                response = client.graphql(query)

                prs = PullRequest.process(response, repo_name, progress_bar)
                for pr in prs:
                    if pr.author not in prs_by_author:
                        prs_by_author[pr.author] = []
                    prs_by_author[pr.author].append(pr)

                repo_has_next_page = response['data']['search']['pageInfo']['hasNextPage']
                if not repo_has_next_page:
                    break
                cursor = response['data']['search']['pageInfo']['endCursor']

        return prs_by_author

    @staticmethod
    def process(response, repo_name, progress_bar = None):
        raw_prs = response['data']['search']['edges']

        prs = []
        for pr_data in raw_prs:
            raw_pr = pr_data['node']

            # only count PR's that have author data
            if 'author' in raw_pr:
                pr = PullRequest.from_response(raw_pr, repo_name)
                if pr: # could return None
                    prs.append(pr)
            if progress_bar is not None:
                progress_bar.count += 1

        return prs

    @staticmethod
    def from_response(pr, repo_name):
        if pr['author'] and 'login' in pr['author']:
            author = pr['author']['login']

            if 'email' in pr['author']:
                author_email = pr['author']['email']
            else:
                author_email = None

            pr_title = pr['title']
            pr_number = pr['number']

            if author_email:
                if 'name' in pr['author']:
                    author_name = pr['author']['name']
                else:
                    author_name = author  # if no name is provided, set name to github username

                pr_created = datetime.strptime(
                    pr['createdAt'], '%Y-%m-%dT%H:%M:%SZ').date()
                pr_closed = datetime.strptime(
                    pr['closedAt'], '%Y-%m-%dT%H:%M:%SZ').date()

                labels_raw = pr['labels']['nodes']
                if len(labels_raw) > 0:
                    labels = [label['name'] for label in labels_raw]
                else:
                    labels = []

                logger.debug(
                    f"We found a PR labeled {labels} #{pr_number} {pr_title}")

                pr_data = dict(author=author, repo=repo_name, author_email=author_email, author_name=author_name, number=pr_number,
                                title=pr_title, created_at=pr_created, closed_at=pr_closed, labels=labels)

                pr = PullRequest(**pr_data)

                return pr
            else:
                logger.debug(f"We have an PR with no author email: [{author}] #{pr_number} {pr_title}")
        else:
            logger.debug(f"Skipping PR, no author probably dependabot: {pr['title']}")

        return None


    @staticmethod
    def get_by_repo(org, lookback_days=None, global_exclude=None, offline=False):
        # this needs to be manually dumped with the graphql explorer
        # https://docs.github.com/en/graphql/overview/explorer
        prs_by_repo = {}
        # TODO: mock offline out in a test
        if offline:
            with open("pr_dump.json", "r") as f:
                repositories = ['edgex-ui-go']
                response = json.load(f)
                for repo in repositories:
                    prs_by_author = {}
                    prs = PullRequest.process(response, repo)
                    for pr in prs:
                        if pr.author not in prs_by_author:
                            prs_by_author[pr.author] = []
                        prs_by_author[pr.author].append(pr)

                    if len(prs_by_author) > 0:
                        prs_by_repo[repo] = prs_by_author
                    else:
                        prs_by_repo[repo] = None
        else:
            client = API.get_client()
            repositories = PullRequest.get_org_repos(client, org, global_exclude)
            
            if lookback_days is not None:
                end_date = API.get_date(lookback_days)
            else:
                end_date = None

            logger.info(f"Searching through [{len(repositories)}] repos...")
            
            for repo in repositories:
                if end_date is not None:
                    logger.info(f"[{repo}] Querying GitHub API to find PR's before: [{end_date}], [{lookback_days}] day(s) ago")
                else:
                    logger.info(f"[{repo}] Querying GitHub API to find ALL eligable PR's")

                prs_by_author = PullRequest.get_repo_prs(client, org, repo, end_date)
                
                if prs_by_author and len(prs_by_author) > 0:
                    prs_by_repo[repo] = prs_by_author
                else:
                    prs_by_repo[repo] = None

        return prs_by_repo
