import click
import csv
import yaml

DATA_PATH = 'oscars.csv'

FIELDNAMES = [
    'Ceremony',
    'Year',
    'Class',
    'Canonical Category',
    'Category',
    'NomId',
    'Film',
    'FilmId',
    'Name',
    'Nominee(s)',
    'NomineeIds',
    'Winner',
    'Detail',
    'Placement',
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
            if k == 'Detail':
                new_entry[k] = ' / '.join(v)
            elif k == 'Nominee(s)':
                new_entry[k] = ', '.join(v)
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


def read_lookup_dict(filepath, lower=False):
    d = {}
    for k, values in yaml.safe_load(open(filepath)).items():
        for v in values:
            if lower:
                d[v.lower()] = k
            else:
                d[v] = k
    return d


def get_letters(s, lower=False):
    letters = ''.join(c for c in s if c.isalpha())
    if lower:
        return letters.lower()
    else:
        return letters
