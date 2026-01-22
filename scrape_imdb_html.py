#!/usr/bin/python3
import argparse
import re
import yaml
import json
import pathlib
import requests
import click
from tqdm import tqdm

WIDGET_PATTERN = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*)</script>')
SONG_PATTERNS = [
    re.compile(r'[Ss]ong:? "([^"]*)"'),
    re.compile(r'For "([^"]*)"'),
]


def parse_imdb_html(s):
    D = {'awards': {}}
    m = WIDGET_PATTERN.search(s)
    data_s = m.group(1)
    needle = '</script>'
    if needle in data_s:
        i = data_s.index(needle)
        data_s = data_s[:i]

    ddd = json.loads(data_s)
    edition = ddd['props']['pageProps']
    edition_info = edition['editionInfo']
    D['id'] = edition_info['id']
    D['year'] = edition_info['year']
    D['name'] = edition_info['event']['name']['text']
    D['location'] = edition_info['event']['location']['text']
    D['date'] = edition_info['dateRange']['startDate']['dateComponents']
    del D['date']['__typename']

    for award in edition['edition']['awards']:
        for edge in award['nominationCategories']['edges']:
            node = edge['node']
            if node['category']:
                cat = node['category']['text']
            else:
                cat = award['text']
            nominations = []
            for nomination in node['nominations']['edges']:
                entities = nomination['node']['awardedEntities']
                nom_d = {}
                for key in ['awardTitles', 'awardNames', 'secondaryAwardNames', 'secondaryAwardTitles']:
                    for d in entities.get(key) or []:
                        if 'title' in d:
                            name = d['title']['titleText']['text']
                            value = d['title']['id']
                        else:
                            name = d['name']['nameText']['text']
                            value = d['name']['id']

                        if value in nom_d:
                            click.secho(f'Duplicate for nominee: {name}/{value} in {cat} {D['year']}', fg='yellow')

                        nom_d[value] = name

                # Parse Song Name
                if 'song' in cat.lower() and 'score' not in cat.lower():
                    if len(nomination.get('songNames', [])) == 1:
                        nom_d['song'] = nomination['songNames'][0]
                    else:
                        note = nomination['node']['notes']['plainText']
                        if note:
                            for pattern in SONG_PATTERNS:
                                m = pattern.search(note)
                                if m:
                                    nom_d['song'] = m.group(1)
                                    break
                            else:
                                click.secho(f'Unable to parse song name: {note}', fg='yellow')
                if nom_d:
                    nominations.append(nom_d)
            if nominations:
                if cat in D:
                    D['awards'][cat].update(nominations)
                else:
                    D['awards'][cat] = nominations
    return D


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--force', action='store_true')
    args = parser.parse_args()

    imdb_data = {}
    years = range(1927, 2026)
    pbar = tqdm(years)

    EDGE_CASE_URLS = {
        # Oscars year : Imdb URL
        1927: '1929/1',  # Ceremony 1
        1928: '1930/1',  # Ceremony 2
        1929: '1930/2',  # Ceremony 3
        # 1930: '1931/1'   Ceremony 4
        # 1931: '1932/1'   Ceremony 5
        1932: '1934/1',  # Ceremony 6
        1933: None,
        # 1934: '1935/1', Ceremony 7
    }

    imdb_src = pathlib.Path('imdb_src')
    imdb_src.mkdir(exist_ok=True)
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 '
                             '(KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

    for year in pbar:
        pbar.set_description(str(year))
        year_s = EDGE_CASE_URLS.get(year, f'{year + 1}/1')
        if not year_s:
            continue
        url = f'https://www.imdb.com/event/ev0000003/{year_s}/?ref_=ev_eh'
        fn = imdb_src / f'{year}.html'
        if not fn.exists() or args.force:
            click.secho(f'Downloading {url}...', fg='blue')
            req = requests.get(url, headers=headers)
            with open(fn, 'wb') as f:
                f.write(req.content)
        s = open(fn).read()
        D = parse_imdb_html(s)

        if D:
            imdb_data[year] = D

    def find_category(nom_id, year):
        for cat, data in imdb_data[year].items():
            if nom_id in data:
                return cat

    imdb_data_path = pathlib.Path('imdb_data')
    imdb_data_path.mkdir(exist_ok=True)

    for year in imdb_data:
        destination_path = imdb_data_path / f'{year}.yaml'
        yaml.safe_dump(imdb_data[year], open(destination_path, 'w'), allow_unicode=True)
