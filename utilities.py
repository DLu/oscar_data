import bs4
import click
import csv
import yaml

DATA_PATH = 'oscars.csv'

FIELDNAMES = [
    'Ceremony',
    'Year',
    'Class',
    'CanonicalCategory',
    'Category',
    'NomId',
    'Film',
    'FilmId',
    'Name',
    'Nominees',
    'NomineeIds',
    'Winner',
    'Detail',
    'Note',
    'Citation',
    'MultifilmNomination'
]


def read_csv(filepath=DATA_PATH):
    awards = []
    for row in csv.DictReader(open(filepath), delimiter='\t', doublequote=False, escapechar='\\'):
        for k, v in row.items():
            if not v:
                row[k] = ''
        awards.append(row)
    return awards


def format_for_csv(entry):
    new_entry = {}
    for k, v in entry.items():
        if isinstance(v, list):
            if k in ['Nominees', 'NomineeIds', 'Detail', 'Note']:
                new_entry[k] = '|'.join(v)
            else:
                click.secho(f'Unknown list value: {k}: {v}', fg='red')
        elif isinstance(v, str):
            new_entry[k] = v
        else:
            new_entry[k] = str(v)

    return new_entry


def write_csv(awards, filepath=DATA_PATH):
    with open(filepath, 'w') as f:
        writer = csv.DictWriter(f, FIELDNAMES, delimiter='\t', doublequote=False, escapechar='\\')
        writer.writeheader()
        for row in awards:
            writer.writerow(format_for_csv(row))

    # Remove whitespace from the ends of lines
    with open(filepath, 'r') as f:
        s = f.read()

    while '\t\n' in s:
        s = s.replace('\t\n', '\n')

    with open(filepath, 'w') as f:
        f.write(s)


def remove_enclosing(text, chars=['{}', '[]', '""']):
    match_dict = {s[0]: s[1] for s in chars}
    while text and text[0] in match_dict and match_dict[text[0]] == text[-1] and text[0] not in text[1:-1]:
        text = text[1:-1]
    return text


def read_lookup_dict(filepath, lower_lookup=False):
    d = {}
    for k, values in yaml.safe_load(open(filepath)).items():
        for v in values:
            if lower_lookup:
                d[v.lower()] = k
            d[v] = k
    return d


def find_by_class(soup, name, class_name):
    return soup.find(name, {'class': class_name})


def find_all_by_class(soup, name, class_name):
    return soup.find_all(name, {'class': class_name})


class BeautifulParser(bs4.BeautifulSoup):
    def __init__(self, obj):
        bs4.BeautifulSoup.__init__(self, obj, 'lxml')

    def find_by_class(self, name, class_name):
        return find_by_class(self, name, class_name)

    def find_all_by_class(self, name, class_name):
        return find_all_by_class(self, name, class_name)
