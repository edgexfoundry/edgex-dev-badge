import os
import logging
import json
import re

from datetime import datetime
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

from .base import Base

logger = logging.getLogger(__name__)

class PullRequest(Base):
    def __init__(self, **entries):
        super(PullRequest, self).__init__(**entries)

        # time to close, datediff
        # might be useful in the future if we want to create
        # tiggers for #of days open
        self.ttc = self.closed_at - self.created_at

    @staticmethod
    def get_client():
        try:
            gh_token = os.getenv('GH_TOKEN_PSW')

            token = f"bearer {gh_token}"

            transport = RequestsHTTPTransport(
                url='https://api.github.com/graphql', headers={'Authorization': token})
            client = Client(transport=transport)
            return client
        except KeyError:
            print("Please provide [GH_TOKEN_PSW] env var")
            raise KeyError

    # GitHub & labels together, I want to | them
    #, $prLabels: String!
    #, labels:[$prLabels]
    @staticmethod
    def get_repo_pr_query():
        return '''
query($repoQuery: String!, $numPrs: Int!) {
search(query: $repoQuery, type: REPOSITORY, first: 100) {
    repositoryCount
    edges {
    node {
        ... on Repository {
        name
        pullRequests(first: $numPrs, states: [MERGED], orderBy: {field: CREATED_AT, direction: DESC}) {
            totalCount
            nodes {
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
}
}
'''

    @staticmethod
    def get_by_repo(org, max_prs=30, global_exclude=None, offline=False):
        if offline:
            with open("pr_dump.json", "r") as f:
                repo_search = json.load(f)
        else:
            client = PullRequest.get_client()
            q = PullRequest.get_repo_pr_query()
            query = gql(q)

            variables = dict(
                repoQuery=f"org:{org} archived:false", numPrs=int(max_prs))
            repo_search = client.execute(query, variable_values=variables)

        if not offline:
            with open("pr_dump.json", "w") as f:
                json.dump(repo_search, f)

        total_repos_search = repo_search['search']['repositoryCount']
        logger.info(f"Searching through [{total_repos_search}] repos...")

        prs_by_repo = {}
        for edges in repo_search['search']['edges']:
            repo = edges['node']
            repo_name = repo['name']
            if global_exclude is None or not global_exclude.match(repo_name):
                # total_prs = repo['pullRequests']['totalCount']
                prs = repo['pullRequests']['nodes']

                pr_by_user = {}
                for pr in prs:
                    # if the pr has an author, then we are ok
                    if 'author' in pr:
                        if pr['author'] and 'login' in pr['author']:
                            author = pr['author']['login']

                            if 'email' in pr['author']:
                                author_email = pr['author']['email']
                            else:
                                author_email = None

                            if 'name' in pr['author']:
                                author_name = pr['author']['name']
                            else:
                                author_name = None

                            pr_title = pr['title']
                            pr_number = pr['number']

                            if author_email:
                                pr_created = datetime.strptime(
                                    pr['createdAt'], '%Y-%m-%dT%H:%M:%SZ').date()
                                pr_closed = datetime.strptime(
                                    pr['closedAt'], '%Y-%m-%dT%H:%M:%SZ').date()

                                if author not in pr_by_user:
                                    pr_by_user[author] = []

                                labels_raw = pr['labels']['nodes']
                                if len(labels_raw) > 0:
                                    labels = [label['name']
                                            for label in labels_raw]
                                else:
                                    labels = []

                                logger.debug(
                                    f"We found a PR labeled {labels} #{pr_number} {pr_title}")

                                pr_data = dict(author=author, repo=repo_name, author_email=author_email, author_name=author_name, number=pr_number,
                                            title=pr_title, created_at=pr_created, closed_at=pr_closed, labels=labels)

                                pr = PullRequest(**pr_data)
                                pr_by_user[author].append(pr)
                            else:
                                logger.debug(f"We have an PR with no author email: [{author}] #{pr_number} {pr_title}")
                        else:
                            logger.debug(f"Skipping PR, no author probably dependabot: {pr['title']}")

                if len(pr_by_user) > 0:
                    prs_by_repo[repo_name] = pr_by_user
                else:
                    prs_by_repo[repo_name] = None

        return prs_by_repo
