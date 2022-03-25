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
        x = x.replace('\x92', '')
        d = yaml.safe_load(x)[1]['nomineesWidgetModel']['eventEditionSummary']
        for award in d['awards']:
            for category in award['categories']:
                if category['categoryName'] == 'None':
                    category['categoryName'] = None
                cname = category['categoryName'] or award['awardName']
                if cname == 'Juvenile Award':
                    cname = 'Special Award'
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
    years = range(1927, 2022)
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
        if year == 1941:
            D['Best Effects, Special Effects']['an0056889a'] = {
                'nm0005738': 'Byron Haskin',
                'nm0506080': 'Nathan Levinson',
                'tt0033537': 'Dive Bomber'
            }

        if D:
            imdb_data[year] = D

    for nom_id, start_year, end_year in [('an1618957', 2020, 2019),
                                         ('an1618959', 2020, 2019),
                                         ('an0600656', 1956, 1957),
                                         ('an0368019', 1985, 1986),
                                         ]:
        if start_year not in imdb_data or end_year not in imdb_data:
            continue
        cat = [cat for (cat, data) in imdb_data[start_year].items() if nom_id in data][0]
        if cat not in imdb_data[end_year]:
            imdb_data[end_year][cat] = {}
        imdb_data[end_year][cat][nom_id] = imdb_data[start_year][cat][nom_id]
        del imdb_data[start_year][cat][nom_id]

    for nom_id0, nom_id1, year0, year1 in [('an0049414', 'an0811120', 1978, 1977),
                                           ('an0050768', 'an0050769', 1990, 1990),
                                           ]:
        if year0 not in imdb_data or year1 not in imdb_data:
            continue
        cat0 = [cat for (cat, data) in imdb_data[year0].items() if nom_id0 in data][0]
        cat1 = [cat for (cat, data) in imdb_data[year1].items() if nom_id1 in data][0]
        imdb_data[year0][cat0][nom_id0].update(imdb_data[year1][cat1][nom_id1])
        del imdb_data[year1][cat1][nom_id1]

    imdb_data_path = pathlib.Path('imdb_data')
    imdb_data_path.mkdir(exist_ok=True)

    for year in imdb_data:
        destination_path = imdb_data_path / f'{year}.yaml'
        yaml.safe_dump(imdb_data[year], open(destination_path, 'w'), allow_unicode=True)
