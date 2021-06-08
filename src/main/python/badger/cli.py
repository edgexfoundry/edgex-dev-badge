import json
import logging
import os
import re
import yaml

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from badger import Badge
from badger import PullRequest

logger = logging.getLogger(__name__)

def parse_args():
    parser = ArgumentParser(
        formatter_class=ArgumentDefaultsHelpFormatter,
        description='Rules based GitHub badge scanner')

    parser.add_argument('--org', required=False, default='edgexfoundry',
                        help=('The organization to lookup'))

    parser.add_argument('--badges', required=False, default='./badges.yaml',
                        help=('badge file to lookup rules'))

    parser.add_argument('--max-prs', required=False, default=30,
                        help=('maximum number of PRs to check per repo. Over 30 and you may start seeing timeouts'))

    parser.add_argument('--execute', action='store_true',
        help='execute processing - not setting is same as running in NOOP mode')

    return parser.parse_args()

def load_config(path='./badges.yaml'):
    if os.access(path, os.R_OK):
        with open(path, 'r') as stream:
            return yaml.safe_load(stream)

def set_logging(args):
    """ configure logging
    """
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)

    logfile = f"{os.getenv('PWD')}/badger-{args.org}.log"
    file_handler = logging.FileHandler(logfile)
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    rootLogger.addHandler(file_handler)

def main():
    args = parse_args()
    set_logging(args)

    badge_yaml = load_config(args.badges)

    global_exclude = None
    if 'global' in badge_yaml:
        if 'exclude' in badge_yaml['global']:
            global_exclude = re.compile(badge_yaml['global']['exclude'])

    prs_by_repo = PullRequest.get_by_repo(args.org, args.max_prs, global_exclude)

    winners_by_badge = {
        'count': 0,
        'results': {}
    }

    badges = Badge.from_yaml(badge_yaml)
    for badge in badges:
        if badge.enabled:
            winners = badge.process(args.org, prs_by_repo, args.execute)
            if len(winners) > 0:
                winners_by_badge['count'] += 1
                winners_by_badge['results'][badge.id] = winners

    print(json.dumps(winners_by_badge))


if __name__ == "__main__":
    main()
