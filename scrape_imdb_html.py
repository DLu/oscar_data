#!/usr/bin/python3
import argparse
import re
import yaml
import pathlib
import requests
import click
from tqdm import tqdm

WIDGET_PATTERN = re.compile(r'IMDbReactWidgets\.NomineesWidget\.push\((.*)\);\n')
SONG_PATTERN = re.compile(r'[Ss]ong:? "([^"]*)"')


def parse_imdb_html(s):
    D = {}
    for x in WIDGET_PATTERN.findall(s):
        x = x.replace('\x92', '').replace('\x97', '')
        d = yaml.safe_load(x)[1]['nomineesWidgetModel']['eventEditionSummary']
        for award in d['awards']:
            for category in award['categories']:
                if category['categoryName'] == 'None':
                    category['categoryName'] = None
                cname = category['categoryName'] or award['awardName']
                nominations = {}
                for nomination in category['nominations']:
                    nom_id = nomination['awardNominationId']
                    nom_d = {}
                    for key in ['primaryNominees', 'secondaryNominees']:
                        for d in nomination[key]:
                            if d['const'] in nom_d:
                                click.secho('Duplicate for nominee: ' + d['const'])
                            nom_d[d['const']] = d['name']

                    # Parse Song Name
                    if 'song' in cname.lower() and 'score' not in cname.lower():
                        if len(nomination['songNames']) == 1:
                            nom_d['song'] = nomination['songNames'][0]
                        else:
                            note = (nomination.get('notes') or '').strip()
                            if note:
                                m = SONG_PATTERN.search(note)
                                if m:
                                    nom_d['song'] = m.group(1)
                                else:
                                    click.secho(f'Unable to parse song name for {nom_id}: {note}', fg='yellow')
                    if nom_d:
                        if nom_id == 'an0475546':
                            del nom_d['tt0037059']
                        multiple_titles = [k for k in nom_d if 'tt' in k]
                        if len(multiple_titles) > 1:
                            other_fields = {k: v for (k, v) in nom_d.items() if 'tt' not in k}
                            for i, key in enumerate(multiple_titles):
                                new_nom_id = nom_id + chr(ord('a') + i)
                                new_nom = dict(other_fields)
                                new_nom[key] = nom_d[key]
                                nominations[new_nom_id] = new_nom
                        else:
                            nominations[nom_id] = nom_d
                if nominations:
                    if cname in D:
                        D[cname].update(nominations)
                    else:
                        D[cname] = nominations
    return D


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--force', action='store_true')
    args = parser.parse_args()

    imdb_data = {}
    years = range(1927, 2023)
    pbar = tqdm(years)

    extra_imdb_data = yaml.safe_load(open('aux_data/extra_imdb_data.yaml'))
    new_nomination_counter = 0

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

    for year in pbar:
        pbar.set_description(str(year))
        year_s = EDGE_CASE_URLS.get(year, f'{year + 1}/1')
        if not year_s:
            continue
        url = f'https://www.imdb.com/event/ev0000003/{year_s}/?ref_=ev_eh'
        fn = pathlib.Path(f'imdb_src/{year}.html')
        if not fn.exists() or args.force:
            click.secho(f'Downloading {url}...', fg='blue')
            req = requests.get(url)
            with open(fn, 'wb') as f:
                f.write(req.content)
        s = open(fn).read()
        D = parse_imdb_html(s)

        for category, entries in extra_imdb_data['missing'].get(year, {}).items():
            if category not in D:
                D[category] = {}
            for film_id, title in entries.items():
                nom_id = f'anxxx{new_nomination_counter:03d}'
                new_nomination_counter += 1
                D[category][nom_id] = {film_id: title}

        if D:
            imdb_data[year] = D

    def find_category(nom_id, year):
        for cat, data in imdb_data[year].items():
            if nom_id in data:
                return cat

    for year_map in extra_imdb_data['year_maps']:
        from_year = year_map['from_year']
        to_year = year_map['to_year']
        if from_year not in imdb_data or to_year not in imdb_data:
            continue
        nom_id = year_map['nom_id']
        cat = find_category(nom_id, from_year)
        entry = imdb_data[from_year][cat][nom_id]
        del imdb_data[from_year][cat][nom_id]

        if 'target_id' in year_map:
            # Merge with existing entry
            target_id = year_map['target_id']
            new_cat = find_category(target_id, to_year)
            imdb_data[to_year][new_cat][target_id].update(entry)
        else:
            # Just move to new year
            if cat not in imdb_data[to_year]:
                imdb_data[to_year][cat] = {}
            imdb_data[to_year][cat][nom_id] = entry

    imdb_data_path = pathlib.Path('imdb_data')
    imdb_data_path.mkdir(exist_ok=True)

    for year in imdb_data:
        destination_path = imdb_data_path / f'{year}.yaml'
        yaml.safe_dump(imdb_data[year], open(destination_path, 'w'), allow_unicode=True)
