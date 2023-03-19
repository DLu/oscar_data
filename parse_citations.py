#!/usr/bin/python3
import re
import click
import pathlib
import yaml

from utilities import read_csv, write_csv

TRANSITION_WORDS = r'(in recognition|whose|for|in appreciation)'
MOSTLY_CAPS = re.compile('^[2A-Z].*[A-Z.]$')
LOWER_MATCH = re.compile(r'[a-z]')
DEDICATION = re.compile(r'To (.*[A-Z]{3,}) ' + TRANSITION_WORDS + r' (.*)')
DEDICATION2 = re.compile(r'To ([^,:\-]+)[,:\-] (.*)')
DEDICATION3 = re.compile(r'To (.*),? ' + TRANSITION_WORDS + r' (.*)')

DEPARTMENTS = yaml.safe_load(open('aux_data/departments.yaml'))


def get_nominees(cite):
    words = cite.split()
    if len(words) <= 4 and ',' not in cite:
        return [cite]
    m = DEDICATION.match(cite)
    if m:
        names = []
        current = []
        for word in m.group(1).split():
            append = False
            if word[-1] == ',':
                word = word[:-1]
                append = True

            if not word:
                continue
            if MOSTLY_CAPS.match(word):
                current.append(word)
            elif word == 'and':
                append = True
            if append and current:
                names.append(' '.join(current))
                current = []
        if current:
            names.append(' '.join(current))
        return names
    m = DEDICATION2.match(cite)
    if m:
        return [m.group(1)]
    m = DEDICATION3.match(cite)
    if m:
        return [m.group(1)]


def get_cite_hash(cite):
    s = ''.join(c for c in cite if c.isalpha())
    a = s[2:5].upper()
    b = f'{len(cite):03d}'
    c = s[-3:].lower()
    return a + b + c


def parse_citations(entry, nom_key='Nominees', debug=False):
    cite = entry.get('Citation', '')

    nominees = get_nominees(cite)
    if nominees:
        new_noms = []
        for nom in nominees:
            m = LOWER_MATCH.search(nom)
            if not m:
                nom = nom.title()
            for suffix in DEPARTMENTS:
                nom = nom.replace(suffix, '').strip()
            new_noms.append(nom)
        nominees = new_noms
        nom_s = ', '.join(nominees)
        if entry.get(nom_key) and entry[nom_key] != nom_s:
            click.secho(f'Duplicate {nominees} {entry[nom_key]}', fg='red')
        else:
            entry[nom_key] = nom_s
            if debug:
                click.secho(entry[nom_key], fg='blue')


if __name__ == '__main__':
    citations_path = pathlib.Path('aux_data/citations.yaml')
    if citations_path.exists():
        citations = yaml.safe_load(open(citations_path))
    else:
        citations = {}

    o_noms = read_csv()

    for nom in o_noms:
        cite = nom.get('Citation', '')
        if not cite:
            continue
        year = nom['Year']
        if year not in citations:
            citations[year] = {}

        key = get_cite_hash(cite)
        if key in citations[year]:
            citation = citations[year][key]
            saved_cite = citation['Citation']
            if saved_cite != cite:
                click.secho(f'Cite Hash Collision! Key: {key} Year: {year}', fg='yellow')
                click.secho(f'\t{saved_cite}', fg='white')
                click.secho(f'\t{cite}', fg='white')
                continue
            nom.update(citation)
        else:
            click.secho(f'New citation: {year}/{key}', fg='blue')
            parse_citations(nom)
            citations[year][key] = {k: v for (k, v) in nom.items() if k in ['Citation', 'Film', 'Nominees'] and v}

    yaml.safe_dump(citations, open(citations_path, 'w'), allow_unicode=True)

    write_csv(o_noms)
