import click
import csv

DATA_PATH = 'oscars.csv'

FIELDNAMES = [
    'Ceremony',
    'Year',
    'Class',
    'Category',
    'Film',
    'Name',
    'Nominee(s)',
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
