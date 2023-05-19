from scrape_imdb_html import parse_imdb_html
import argparse
import click
import pathlib
import requests
import re
import yaml
import csv

WIDGET_PATTERN = re.compile(r'IMDbReactWidgets\.EventHistoryWidget\.push\((.*)\);\n')
HEADING_PATTERN = re.compile(r'<h1>(.*)</h1>')
TITLE_PATTERN = re.compile(r'<div class="event-year-header__year">(\d+) Awards</div>')


def grab(event_code, year=None):
    url = f'https://www.imdb.com/event/{event_code}'
    filestem = event_code
    if year:
        url += f'/{year}/?ref_=ev_eh'
        year_s = year.replace('/', '_')
        filestem += f'_{year_s}'

    fn = pathlib.Path(f'imdb_src/{filestem}.html')
    if not fn.exists() or args.force:
        click.secho(f'Downloading {url}...', fg='blue')
        req = requests.get(url)
        with open(fn, 'wb') as f:
            f.write(req.content)
    return open(fn).read()


def read_metadata(s):
    m = HEADING_PATTERN.search(s)
    name = m.group(1)
    years = []
    for x in WIDGET_PATTERN.findall(s):
        x = x.replace('\x92', '')
        d = yaml.safe_load(x)[1]['eventHistoryWidgetModel']
        for ed in d['eventEditions']:
            years.append('{year}/{instanceWithinYear}'.format(**ed))

    return name, sorted(years)


parser = argparse.ArgumentParser()
parser.add_argument('event_code')
parser.add_argument('-f', '--force', action='store_true')
args = parser.parse_args()

s = grab(args.event_code)
name, years = read_metadata(s)
output_path = f'{name}.csv'
with open(output_path, 'w') as f:
    writer = csv.DictWriter(f, ['Ceremony', 'Year', 'Category', 'NomId', 'Film', 'FilmId',
                                'Nominees', 'NomineeIds', 'Detail'],
                            delimiter='\t', doublequote=False, escapechar='\\')
    writer.writeheader()

    for i, year_s in enumerate(years):
        print(year_s)
        s = grab(args.event_code, year_s)
        m = TITLE_PATTERN.search(s)
        year = m.group(1)
        base = {
            'Ceremony': str(i + 1),
            'Year': year,
        }
        D = parse_imdb_html(s)
        for category, noms in D.items():
            new_base = dict(base)
            new_base['Category'] = category
            for nom_id, nom in noms.items():
                row = dict(new_base)
                row['NomId'] = nom_id
                titles = {}
                nominees = {}
                for k, v in nom.items():
                    if k.startswith('tt'):
                        titles[k] = v
                    elif k.startswith('nm') or k.startswith('co'):
                        nominees[k] = v
                    elif k == 'song':
                        row['Detail'] = v
                    else:
                        print(k, v)
                        exit(0)
                row['Film'] = ','.join(titles.values())
                row['FilmId'] = ','.join(titles.keys())
                row['Nominees'] = ','.join(nominees.values())
                row['NomineeIds'] = ','.join(nominees.keys())
                writer.writerow(row)
