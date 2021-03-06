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

import json
import logging
import os
import pandas as pd
import re
import yaml

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from datetime import date
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

    parser.add_argument('--winners-json', required=False, default='./winners.json',
                        help=('File to write winners json to'))

    parser.add_argument('--winners-csv', required=False, default='./winners.csv',
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

def generate_credly_csv(winner_file, winners_by_badge):
    if winners_by_badge['count'] > 0:
        print(f"Writing CSV file to: {winner_file}")
        all_winners = []
        issue_date = date.today().strftime('%m/%d/%Y')
        for badge_id in winners_by_badge['results']:
            badge_data = winners_by_badge['badge_details'][badge_id]
            credly_id = badge_data['credly_id']
            for winner in winners_by_badge['results'][badge_id]:
                if winner['name'] != 'None':
                    full_name_split = winner['name'].split(' ')
                    first_name = full_name_split[0]
                    last_name = " ".join(full_name_split[1:])
                else:
                    first_name = winner['author']
                    last_name = ''
                
                winner_data = [credly_id, winner['email'],
                            first_name, last_name, issue_date]
                
                # add empty for rest of columns
                for i in range(11): winner_data.append('')

                all_winners.append(winner_data)

        raw_columns = "Badge Template ID,Recipient Email,Issued to First Name,Issued to Last Name,Issued at,Expires at,Issuer Earner ID,Country,State or Province,Evidence Name,Evidence URL,URL Evidence Description,Text Evidence Title,Text Evidence Description,Id Evidence Title,Id Evidence Description"
        columns = raw_columns.split(',')

        credly_data = pd.DataFrame(all_winners, columns=columns)
        credly_data.to_csv(winner_file, index=False)
    else:
        print("No winner csv data to write to csv")

def generate_json(winner_file, winners_by_badge):
    with open(winner_file, 'w') as file:
        json.dump(winners_by_badge, file)

def main():
    print(color(give_me_a_badger(), fg='orange'))
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
                    'credly_id': badge.credly_id
                }

    generate_credly_csv(args.winners_csv, winners_by_badge)
    generate_json(args.winners_json, winners_by_badge)

    print("===============================================")
    print(f"Badger complete...Found [{total_winners}] winners. Check the {args.winners_json} file")


if __name__ == "__main__":
    main()
