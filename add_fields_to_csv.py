#!/usr/bin/python3
import click
import collections
import re
import yaml

from utilities import read_csv, read_lookup_dict, write_csv

SCORE_PATTERN = re.compile(r'([^,]+), ([^,]+), (head of department|musical director) \(([^)]+)\)')
DEPARTMENTS = yaml.safe_load(open('aux_data/departments.yaml'))
SUFFIXES = yaml.safe_load(open('aux_data/suffixes.yaml'))
SPLITS = yaml.safe_load(open('aux_data/hardcode_splits.yaml'))
COUNTRIES = yaml.safe_load(open('aux_data/countries.yaml'))

IGNORABLE_MEMBERS = {
    'producer',
    'producers',
    'co-producer',
    'co-producers',
    'sound director',
    'executive producer',
    'story',
    'song score',
}


def split_nominees(s, nom):
    if s in SPLITS:
        return SPLITS[s]

    s = s.replace('Music and ', 'MusicAnd')
    if s and s[0] == '(' and s[-1] == ')' and '(' not in s[1:]:
        s = s[1:-1]

    m = SCORE_PATTERN.match(s)
    if m:
        pieces = [m.group(1), m.group(2)]
        paren = m.group(4)
        if paren != 'no composer credit':
            pieces.append(paren)
    else:
        pieces = [s.strip()]
    for splitter in ['&amp;', ',', ' and ', ';', '&']:
        new_pieces = []
        for p in pieces:
            if splitter in p:
                for pp in p.split(splitter):
                    xs = pp.strip()
                    if xs:
                        if xs.startswith('Jr.') and splitter == ',':
                            new_pieces[-1] += ' ' + xs
                        else:
                            new_pieces.append(xs)

            else:
                new_pieces.append(p)
        pieces = new_pieces
    for rsplitter in [' by ', ':']:
        new_pieces = []
        for p in pieces:
            if rsplitter in p:
                new_pieces.append(p.rpartition(rsplitter)[-1].strip())
            else:
                new_pieces.append(p)
        pieces = new_pieces

    # ensure unique and filter
    new_pieces = []
    for p in pieces:
        if p.lower() in IGNORABLE_MEMBERS:
            continue
        if nom['Canonical Category'] == 'INTERNATIONAL FEATURE FILM':
            if p.lower() in COUNTRIES:
                continue
            elif nom['Ceremony'] != '29':
                # 1956 they nominated the producers too
                click.secho(f'Unexpected Country name "{p}" for International Film', fg='yellow')
        if p[0] == '(' and p[-1] == ')':
            p = p[1:-1]
        for suffix in DEPARTMENTS:
            if suffix in p:
                p = p.replace(suffix, '').strip()
                if p == 'Walt Disney':
                    p = 'Walt Disney Studios'

        if p in SPLITS:
            new_pieces += SPLITS[p]
        elif p in SUFFIXES:
            new_pieces[-1] += ' ' + p
        elif p and p not in new_pieces:
            new_pieces.append(p)
    return new_pieces


if __name__ == '__main__':
    canonical_award_names = read_lookup_dict('aux_data/canonical.yaml')
    class_lookup = read_lookup_dict('aux_data/classes.yaml')
    missing_canonical = set()

    o_noms = []
    # Hack to remove one nomination
    for nom in read_csv():
        if nom['Ceremony'] == '1' and nom['Category'] == 'CINEMATOGRAPHY' and nom['Film'] == 'Sunrise':
            # It is considered a single nomination for the film.
            if nom['Name'] == 'Karl Struss':
                continue
            nom['Name'] = 'Charles Rosher, Karl Struss'
        o_noms.append(nom)

    canon_check = collections.defaultdict(dict)

    for nom in o_noms:
        # Add Canonical Category
        ceremony = int(nom['Ceremony'])
        category = nom['Category']
        if category in canonical_award_names:
            canon = canonical_award_names[category]
        elif category in class_lookup:
            canon = category
        else:
            # update capitalization on nominees
            main, _, parenthetical = category.partition('(')
            if parenthetical:
                upper_cat = f'{main.upper()}({parenthetical}'
            else:
                upper_cat = main.upper()
            if upper_cat in class_lookup:
                canon = upper_cat
            else:
                if category not in missing_canonical:
                    click.secho(f'Unknown cat: {category}', fg='yellow')
                    missing_canonical.add(category)
                continue
            # canon = canonical_award_names.get(category, category)
        nom['Canonical Category'] = canon

        # Check for overloading of canon categories
        if canon in canon_check[ceremony] and canon_check[ceremony][canon] != category:
            click.secho(f'Failed canon check {canon} {canon_check[canon]} {category}', fg='red')
        canon_check[ceremony][canon] = category

        # Rewrite the broad award classes
        try:
            nom['Class'] = class_lookup[canon]
        except KeyError:
            click.secho(f'Weird Category: "{canon}" ({category})', fg='red')

        # Extra parsing for name(s)
        name = nom.get('Name', '')
        if name:
            nom['Nominee(s)'] = split_nominees(name, nom)

    write_csv(o_noms)
