#!/usr/bin/python3
import click
import collections
import re
import yaml

from utilities import read_csv, read_lookup_dict, remove_enclosing, write_csv

SCORE_PATTERN = re.compile(r'([^,]+), ([^,]+), (head of department|musical director) \(([^)]+)\)')
PARENTHETICAL_PATTERN = re.compile(r'(.*) \((.*)\)')
DEPARTMENTS = yaml.safe_load(open('aux_data/departments.yaml'))
HARCODED_SPLITS = yaml.safe_load(open('aux_data/hardcode_splits.yaml'))
COUNTRIES = yaml.safe_load(open('aux_data/countries.yaml'))

ROLES_TO_IGNORE = {
    'producer',
    'producers',
    'associate producer',
    'co-producer',
    'co-producers',
    'sound director',
    'executive producer',
    'story',
    'song score',
    'screenplay',
}


def split_nominees(s, nom):
    # Some entities have splitters in their name, so we hardcode them
    if s in HARCODED_SPLITS:
        return HARCODED_SPLITS[s]

    # Preprocessing
    s = s.replace('Music and ', 'MusicAnd')  # Don't split on Music and Lyric (or Music and adaptation score)

    for suffix in ['Jr.', 'Sr.', 'III', 'Inc.']:
        s = s.replace(', ' + suffix, ' ' + suffix)

    s = remove_enclosing(s, chars=['()'])

    m = SCORE_PATTERN.match(s)
    if m:
        # Process the particular pattern for certain MUSIC (scoring) nominations in the 30s
        # Warner Bros. Studio Music Department, Leo Forbstein, head of department (Score by Erich Wolfgang Korngold)
        # becomes
        # Warner Bros. Studio Music Department, Leo Forbstein, Score by Erich Wolfgang Korngold
        pieces = [m.group(1), m.group(2)]
        paren = m.group(4)
        if paren != 'no composer credit':
            pieces.append(paren)
    elif nom['Ceremony'] == '6' and PARENTHETICAL_PATTERN.match(s):
        # Process the ASSISTANT DIRECTORY formatting for this one year
        # Percy Ikerd (Fox) becomes just Percy Ikerd
        m = PARENTHETICAL_PATTERN.match(s)
        pieces = [m.group(1)]
    else:
        pieces = [s.strip()]

    # Processing

    # Split using common delimiters
    for splitter in ['&amp;', ',', ' and ', ';', '&']:
        new_pieces = []
        for piece in pieces:
            if splitter not in piece:
                new_pieces.append(piece)
                continue

            for small_piece in map(str.strip, piece.split(splitter)):
                if not small_piece:
                    continue
                new_pieces.append(small_piece)

        pieces = new_pieces

    # Split using things that indicate a category
    # e.g. Lyrics by Richard M. Sherman should just be Richard M. Sherman
    #      Production Design: Adam Stockhausen should just be Adam Stockhausen
    for rsplitter in [' by ', ':']:
        new_pieces = []
        for piece in pieces:
            if rsplitter in piece:
                new_pieces.append(piece.rpartition(rsplitter)[-1].strip())
            else:
                new_pieces.append(piece)
        pieces = new_pieces

    # ensure unique and filter
    new_pieces = []
    for piece in pieces:
        # If the piece is a role (like producer) we do not include it
        if piece.lower() in ROLES_TO_IGNORE:
            continue

        # We do NOT include the name of the country that won as a nominee
        if nom['CanonicalCategory'] == 'INTERNATIONAL FEATURE FILM':
            if piece.lower() in COUNTRIES:
                continue
            elif nom['Ceremony'] != '29':
                # 1956 they nominated the producers too
                click.secho(f'Unexpected Country name "{piece}" for International Film', fg='yellow')

        # Remove Enclosing Brackets
        piece = remove_enclosing(piece, chars=['()'])

        for suffix in DEPARTMENTS:
            if suffix in piece:
                piece = piece.replace(suffix, '').strip()
                if piece == 'Walt Disney':
                    piece = 'Walt Disney Studios'

        if piece in HARCODED_SPLITS:
            new_pieces += HARCODED_SPLITS[piece]
        elif piece and piece not in new_pieces:
            new_pieces.append(piece)
    return new_pieces


if __name__ == '__main__':
    canonical_award_names = read_lookup_dict('aux_data/canonical.yaml', lower_lookup=True)
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

    # To ensure that the canonical categories are correct, for each ceremony we check that the
    # the CanonicalCategory is only used for one category
    canon_check = collections.defaultdict(dict)

    for nom in o_noms:
        # Add Canonical Category
        ceremony = int(nom['Ceremony'])
        category = nom['Category']
        if category.lower() in canonical_award_names:
            canon = canonical_award_names[category.lower()]
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
        nom['CanonicalCategory'] = canon

        # Check for overloading of canon categories
        if canon in canon_check[ceremony] and canon_check[ceremony][canon] != category.lower():
            click.secho(f'Failed canon check for ceremony {ceremony}: ', fg='red')
            click.secho(f'  {category} maps to {canon}', fg='red')
            click.secho(f'  but that already was mapped from {canon_check[ceremony][canon]}', fg='red')
        canon_check[ceremony][canon] = category.lower()

        # Rewrite the broad award classes
        try:
            nom['Class'] = class_lookup[canon]
        except KeyError:
            click.secho(f'Weird Category: "{canon}" ({category})', fg='red')

        # Extra parsing for name(s)
        name = nom.get('Name', '')
        if name:
            nom['Nominees'] = split_nominees(name, nom)

    write_csv(o_noms)
