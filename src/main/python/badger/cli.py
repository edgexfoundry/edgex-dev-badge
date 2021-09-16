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

#import base64
import json
import logging
import os
#import pyfiglet
import re
import yaml

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from badger import Badge
from badger import PullRequest

from colors import *

logger = logging.getLogger(__name__)

def parse_args():
    parser = ArgumentParser(
        formatter_class=ArgumentDefaultsHelpFormatter,
        description='Rules based GitHub badge scanner')

    parser.add_argument('--org', required=False, default='edgexfoundry',
                        help=('The organization to lookup'))

    parser.add_argument('--badges', required=False, default='./badges.yml',
                        help=('badge file to lookup rules'))

    parser.add_argument('--winners', required=False, default='./winners.json',
                        help=('File to write winners json to'))

    parser.add_argument('--lookback', required=False, type=int, default=30,
                        help=('Lookback window for PRs'))

    parser.add_argument('--no-lookback', action='store_true',
                        help='Do not use lookback window and search all PRs')

    parser.add_argument('--execute', action='store_true',
        help='execute processing - not setting is same as running in NOOP mode')

    return parser.parse_args()

def load_config(path='./badges.yml'):
    if os.access(path, os.R_OK):
        with open(path, 'r') as stream:
            return yaml.safe_load(stream)

def set_logging(args):
    """ configure logging
    """
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)

    logfile = f"./badger-{args.org}.log"
    file_handler = logging.FileHandler(logfile)
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    rootLogger.addHandler(file_handler)

def give_me_a_badger():
    return """
                    ___,,___
           _,-='=- =-  -`"--.__,,.._
        ,-;// /  - -       -   -= - "=.
      ,'///    -     -   -   =  - ==-=\`.
     |/// /  =    `. - =   == - =.=_,,._ `=/|
    ///    -   -    \  - - = ,ndDMHHMM/\b  \\
  ,' - / /        / /\ =  - /MM(,,._`YQMML  `|
 <_,=^Kkm / / / / ///H|wnWWdMKKK#""-;. `"0\  |
        `""QkmernesTOMM|""WHMKKMM\   `--. \> \\
 hjm          `""'  `->>>    ``WHMb,.    `-_<@)
                                `"QMM`.
                                   `>>>
                  I badge so you don't have to.
    """

def main():
    print(color(give_me_a_badger(), fg='orange'))
    #print(pyfiglet.figlet_format('Badger', font='slant'))
    args = parse_args()
    set_logging(args)

    badge_yaml = load_config(args.badges)

    global_exclude = None
    if 'global' in badge_yaml:
        if 'exclude' in badge_yaml['global']:
            global_exclude = re.compile(badge_yaml['global']['exclude'])

    #lookback = int(args.lookback)
    if args.no_lookback:
        lookback = None
    else:
        lookback = args.lookback

    prs_by_repo = PullRequest.get_by_repo(args.org, lookback, global_exclude)

    winners_by_badge = {
        'count': 0,
        'badge_details': {},
        'results': {}
    }

    badges = Badge.from_yaml(badge_yaml)

    total_winners = 0
    for badge in badges:
        if badge.enabled:
            winners = badge.process(args.org, prs_by_repo, args.execute)
            if len(winners) > 0:
                total_winners += len(winners)
                winners_by_badge['count'] += 1
                winners_by_badge['results'][badge.id] = winners

                # with open(f"{script_root}/{badge.image}", "rb") as image_file:
                #     encoded_image = base64.b64encode(image_file.read())

                winners_by_badge['badge_details'][badge.id] = {
                    'display': badge.display,
                    'image_url': badge.image_url,
                    # 'image_base64': encoded_image.decode('utf-8'),
                    'download_url': badge.download_url
                }

    with open(args.winners, 'w') as file:
        json.dump(winners_by_badge, file)
    
    print("===============================================")
    print(f"Badger complete...Found [{total_winners}] winners. Check the {args.winners} file")


if __name__ == "__main__":
    main()
