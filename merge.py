#!/usr/bin/python3
import argparse
import collections
import click
import pathlib
import unidecode
import re
import yaml

from utilities import read_csv, write_csv, read_lookup_dict

PAREN_PATTERN = re.compile(r'^(.*) \((.*)\)$')
COLON_PATTERN = re.compile(r'^(.*): (.*)$')

REMAP = yaml.safe_load(open('aux_data/hardcode.yaml'))
FIRST_NAMES = yaml.safe_load(open('aux_data/first_names.yaml'))
SUFFIXES = yaml.safe_load(open('aux_data/suffixes.yaml'))
COMPANY_LOOKUP = read_lookup_dict('companies.yaml')
COMPANY_CATEGORIES = {
    'BEST PICTURE', 'UNIQUE AND ARTISTIC PICTURE', 'SPECIAL AWARD', 'OUTSTANDING PRODUCTION',
    'SHORT SUBJECT (Comedy)', 'SHORT SUBJECT (Novelty)', 'SHORT SUBJECT (Color)', 'SHORT SUBJECT (One-reel)',
    'SHORT SUBJECT (Two-reel)', 'SHORT FILM (Animated)', 'SOUND RECORDING', 'SOUND', 'MUSIC (Scoring)',
    'SCIENTIFIC OR TECHNICAL AWARD (Class III)', 'SCIENTIFIC OR TECHNICAL AWARD (Class II)',
    'SCIENTIFIC OR TECHNICAL AWARD (Class I)', 'SPECIAL EFFECTS', 'DOCUMENTARY (Short Subject)',
    'DOCUMENTARY (Feature)',
}

CATEGORY_STATS = collections.Counter()
NOM_STATS = collections.Counter()
FILM_STATS = collections.Counter()
NOMINEE_STATS = collections.Counter()
SONG_STATS = collections.Counter()
NAME_MISSES = collections.Counter()


def get_nabble(s):
    if s is None:
        return None
    new_name = ''
    for c in unidecode.unidecode(s).lower():
        if c.isalpha() or c.isdigit():
            new_name += c
    return new_name


def get_nominees(entry, clean=True):
    if entry.get('Nominees', '') == '':
        return
    names = entry['Nominees'].split('|')
    for name in names:
        for prefix in ['sir', 'dame']:
            if name.startswith(prefix):
                name = name = name[len(prefix):]
        if clean:
            yield get_nabble(name)
        else:
            yield name


def get_nominee_ids(entry):
    value = entry.get('NomineeIds')
    count = entry.get('Nominees', '').count('|')
    if not value:
        return ['?'] * count

    if isinstance(value, list):
        return value
    else:
        return value.split('|')


def titles_match(a, b):
    if get_nabble(a) == get_nabble(b):
        return True

    for c, d in [(a, b), (b, a)]:
        if c.startswith('The ') and get_nabble(c[4:]) == get_nabble(d):
            return True
        for pattern in [COLON_PATTERN, PAREN_PATTERN]:
            m = pattern.match(c)
            if m:
                if d in m.groups():
                    return True


def name_split(s):
    parts = s.title().split()
    if parts and parts[0] == 'Dr.':
        parts = parts[1:]

    for suffix in SUFFIXES:
        if parts and parts[-1] == suffix:
            parts = parts[:-1]
    return parts


def first_names_match(a, b, length=3):
    if a == b:
        return True
    if a[:length] == b[:length]:
        return True

    if (len(a) > 1 and a[1] == '.') or (len(b) > 1 and b[1] == '.'):
        if a[0] == b[0]:
            return True

    for row in FIRST_NAMES:
        if a in row and b in row:
            return True


def names_match(a, b):
    if get_nabble(a) == get_nabble(b):
        return True
    a_parts = name_split(a)
    b_parts = name_split(b)
    if a_parts and b_parts and a_parts[-1] == b_parts[-1]:
        if first_names_match(a_parts[0], b_parts[0]):
            return True

    if len(b_parts) == 2:
        if len(a_parts) == 2 and b_parts[0] == a_parts[1] and b_parts[1] == a_parts[0]:
            return True
        if len(a_parts) == 3 and '-' in b_parts[0] and b_parts[-1] == a_parts[0]:
            hyphenate = '-'.join(a_parts[1:])
            if b_parts[0] == hyphenate:
                return True

    if a in b or b in a:
        return True


def get_matching_name(query_name, names_to_noms, match_fn):
    matches = []
    for name in names_to_noms:
        if match_fn(query_name, name):
            matches.append(name)

    # Only if there's one match
    if len(matches) != 1:
        return

    matching_name = matches[0]
    if len(names_to_noms[matching_name]) != 1:
        return

    return matching_name


def get_matching_nominee(o_nom, names_to_noms):
    for nom_name in get_nominees(o_nom, clean=False):
        matching_name = get_matching_name(nom_name, names_to_noms, names_match)
        if matching_name:
            return matching_name


def get_name_match(nom_name, people):
    if nom_name in people:
        return nom_name

    matches = []
    for i_name in people:
        if names_match(nom_name, i_name):
            matches.append(i_name)
    if len(matches) == 1:
        return matches[0]


def match_nomination(o_nom, nom_id, i_nom, speculative=False):
    updates = {'NomId': nom_id}
    titles = [a for a in i_nom if 'tt' in a]
    if o_nom.get('Film'):
        if len(titles) == 1:
            updates['FilmId'] = titles[0]
            titles = []
        elif not speculative:
            click.secho(f'Unable to match film for {o_nom["Category"]}', fg='yellow')
            if args.mode is None or args.mode == 'missing_film_names':
                click.secho(f'Missing Film Name: {o_nom}', fg='red')

    people = {}
    for k, v in i_nom.items():
        if k.startswith('tt') or k == 'song' or v is None:
            continue
        if k in REMAP:
            v = REMAP[k]
        people[v] = k
    original_people_count = len(people)

    nom_ids = {}
    unmatched_names = []
    canon_category = o_nom.get('CanonicalCategory', '')
    nom_names = list(get_nominees(o_nom, clean=False))

    # Special case for "Roderick Jaynes"
    if nom_names == ['Roderick Jaynes'] and people == {'Ethan Coen': 'nm0001053', 'Joel Coen': 'nm0001054'}:
        if not speculative:
            updates['NomineeIds'] = ','.join(people.values())
            o_nom.update(updates)
            NOMINEE_STATS['matched'] += 1
            if o_nom['Film']:
                if 'FilmId' in updates:
                    FILM_STATS['matched'] += 1
                else:
                    FILM_STATS['unmatched'] += 1
        return True

    nom_id_list = get_nominee_ids(o_nom)
    if nom_id_list and not speculative:
        for n_id, nom_name in zip(nom_id_list, nom_names):
            if n_id == '?':
                continue
            nom_ids[nom_name] = n_id
            if nom_name in people:
                del people[nom_name]
            else:
                matching_names = [k for k, v in people.items() if v == n_id]
                if len(matching_names) == 1:
                    del people[matching_names[0]]
    for nom_name in nom_names:
        if nom_name in nom_ids:
            continue
        if canon_category in COMPANY_CATEGORIES and nom_name in COMPANY_LOOKUP:
            nom_ids[nom_name] = COMPANY_LOOKUP[nom_name]
            continue
        matching_name = get_name_match(nom_name, people)
        if matching_name:
            nom_ids[nom_name] = people[matching_name]
            del people[matching_name]
            continue
        unmatched_names.append(nom_name)

    # Special case for multifilm noms
    if o_nom.get('MultifilmNomination'):
        valid = len(nom_ids) > 0
    else:
        valid = not titles and (nom_ids or original_people_count == 0)

    if speculative:
        return valid

    if not valid:
        return valid

    if o_nom['Film']:
        if 'FilmId' in updates:
            FILM_STATS['matched'] += 1
        else:
            FILM_STATS['unmatched'] += 1

    updates['NomineeIds'] = ','.join(nom_ids.get(nom_name, '?') for nom_name in nom_names)
    o_nom.update(updates)

    NOMINEE_STATS['matched'] += len(nom_ids)
    for name in unmatched_names:
        NAME_MISSES[name] += 1
    should_print = args.mode is None
    if people and unmatched_names:
        should_print |= args.mode == 'mismatched_names'
        NOMINEE_STATS['mismatched'] += len(unmatched_names)
    elif people:
        should_print |= args.mode == 'extra_i_names'
        NOMINEE_STATS['extra_i'] += len(people)
    elif unmatched_names:
        should_print |= args.mode == 'extra_o_names'
        NOMINEE_STATS['extra_o'] += len(unmatched_names)
    else:
        should_print = False

    if not args.scitech and o_nom['Class'] == 'SciTech':
        should_print = False
    if args.core and o_nom['Class'] in ['SciTech', 'Special']:
        should_print = False

    if should_print:
        film = o_nom.get('Film', '[NO FILM]')
        category = o_nom['CanonicalCategory']
        click.secho(f'{film} {category}', fg='red')
        if len(people) == 1 and len(unmatched_names) == 1:
            p_name, p_id = list(people.items())[0]
            click.secho(f'\t{nom_id}: {{{p_id}: {unmatched_names[0]}}}  # {p_name}', fg='red')
        else:
            click.secho(f'\t{nom_id}: {people} {unmatched_names}', fg='red')

    return valid


def match_category(o_noms, i_noms, speculative=False):
    o_unmatched = []
    i_unmatched = set(i_noms.keys())
    song_lookup = {}

    names_to_noms = collections.defaultdict(list)

    for nom_id, nom in i_noms.items():
        if nom_id in REMAP:
            if REMAP[nom_id] is None:
                i_unmatched.remove(nom_id)
                continue
            nom.update(REMAP[nom_id])

        for k, v in nom.items():
            if k == 'song':
                song_lookup[get_nabble(v)] = nom_id
                continue
            elif v is None:
                continue
            else:
                names_to_noms[v].append(nom_id)

    for o_nom in o_noms:
        if o_nom.get('CanonicalCategory') == 'MUSIC (Original Song)':
            song_name = get_nabble(o_nom['Detail'])
            if song_name in song_lookup:
                nom_id = song_lookup[song_name]
                del song_lookup[song_name]
                i_unmatched.remove(nom_id)
                if not speculative:
                    SONG_STATS['matched'] += 1
                match_nomination(o_nom, nom_id, i_noms[nom_id], speculative=speculative)
            elif not speculative:
                if args.mode is None or args.mode == 'songs':
                    click.secho(f"Song doesn't match: {o_nom['Detail']} {song_name}", fg='red')
                    click.secho(f'\t{song_lookup}', fg='red')
                SONG_STATS['unmatched'] += 1
                o_unmatched.append(o_nom)
            else:
                o_unmatched.append(o_nom)
            continue

        # Special case just for people who win multiple technical achievement awards in one year
        nom_id = None
        for name, key_phrases in [('RICHARD EDLUND', {'an0053905': 'beam-splitter', 'an0053906': 'Empire Motion'}),
                                  ('IVAN KRUGLAK', {'an0051476': 'Coherent', 'an0051466': 'wireless transmission'}),
                                  ]:
            if not o_nom['Citation'].startswith(f'To {name}'):
                continue
            for k, v in key_phrases.items():
                if k in i_unmatched and v in o_nom['Citation']:
                    nom_id = k
        if nom_id:
            if match_nomination(o_nom, nom_id, i_noms[nom_id], speculative=speculative):
                i_unmatched.remove(nom_id)
            continue

        # Non-Song Matching
        matching_name = None
        if o_nom.get('Film'):
            matching_name = get_matching_name(o_nom['Film'], names_to_noms, titles_match)

        if not matching_name:
            matching_name = get_matching_nominee(o_nom, names_to_noms)

        if matching_name:
            nom_id = names_to_noms[matching_name][0]
            if nom_id in i_unmatched:
                if match_nomination(o_nom, nom_id, i_noms[nom_id], speculative=speculative):
                    i_unmatched.remove(nom_id)
                    del names_to_noms[matching_name]
                    continue

        if o_nom.get('Film') or o_nom.get('Nominees'):
            o_unmatched.append(o_nom)

    o_matched_count = len(o_noms) - len(o_unmatched)
    if speculative:
        i_matched_count = len(i_noms) - len(i_unmatched)
        return (o_matched_count + i_matched_count) / (len(o_noms) + len(i_noms))
    else:
        NOM_STATS['matched'] += o_matched_count
        return o_unmatched, {nom_id: i_noms[nom_id] for nom_id in i_unmatched}


def match_year(oscars, imdb):
    unmatched_o_cats = set()
    unmatched_i_cats = set(imdb.keys())
    unmatched_o_noms = []
    unmatched_i_noms = {}

    def get_matching_category(category, options):
        lower_lookup = {get_nabble(a).replace('oftheyear', ''): a for a in options}
        category = get_nabble(category)

        for prefix in ['', 'best', 'bestachievementin', 'bestperformancebyan']:
            alt = prefix + category
            if alt in lower_lookup:
                return lower_lookup[alt]

    for o_cat in oscars:
        i_cat = get_matching_category(o_cat, imdb)
        if i_cat not in imdb:
            unmatched_o_cats.add(o_cat)
            continue

        unmatched_i_cats.remove(i_cat)
        if args.category_matching:
            click.secho(f'Exact category match:     {o_cat:40s} {i_cat:40s}', bg='green')
        CATEGORY_STATS['exact'] += 1
        ou, iu, = match_category(list(oscars[o_cat]), dict(imdb[i_cat]))
        unmatched_o_noms += ou
        unmatched_i_noms.update(iu)

    full_scores = []
    for o_cat in list(unmatched_o_cats):
        for i_cat in unmatched_i_cats:
            score = match_category(list(oscars[o_cat]), dict(imdb[i_cat]), speculative=True)
            if score > 0.0:
                full_scores.append((score, o_cat, i_cat))

    for score, o_cat, i_cat in sorted(full_scores, reverse=True):
        if o_cat not in unmatched_o_cats or i_cat not in unmatched_i_cats:
            continue
        if args.category_matching:
            click.secho(f'Fuzzy Category Match: {score:.1f} {o_cat:40s} {i_cat:40s}', bg='blue')
        CATEGORY_STATS['fuzzy'] += 1
        ou, iu, = match_category(list(oscars[o_cat]), dict(imdb[i_cat]))
        unmatched_o_noms += ou
        unmatched_i_noms.update(iu)
        unmatched_o_cats.remove(o_cat)
        unmatched_i_cats.remove(i_cat)

    for o_cat in unmatched_o_cats:
        CATEGORY_STATS['extra_o'] += 1
        unmatched_o_noms += oscars[o_cat]

    for i_cat in unmatched_i_cats:
        CATEGORY_STATS['extra_i'] += 1
        unmatched_i_noms.update(imdb[i_cat])

    if args.category_matching:
        click.secho('Leftovers!', bg='blue')
    new_o, new_i = match_category(unmatched_o_noms, unmatched_i_noms, speculative=False)
    NOM_STATS['extra_o'] += len(new_o)
    NOM_STATS['extra_i'] += len(new_i)

    for o_nom in new_o:
        if o_nom['Film']:
            FILM_STATS['misses'] += 1
            if args.mode is None or args.mode == 'film_misses':
                click.secho(f"Unknown film: {o_nom['Film']}", bg='red')
        NOMINEE_STATS['misses'] += len(list(get_nominees(o_nom)))

    if args.mode is None or args.mode == 'category':
        if not args.scitech:
            new_o = [o_nom for o_nom in new_o if o_nom['Class'] != 'SciTech']
        if args.core:
            new_o = [o_nom for o_nom in new_o if o_nom['Class'] not in ['Special', 'SciTech']]
        if new_o:
            click.secho('Oscars Noms (unmatched):', fg='yellow')
            for o_nom in new_o:
                o_cat = o_nom['CanonicalCategory']
                film = o_nom.get('Film', '[x]')
                nominees = o_nom.get('Nominees', '<>')
                click.secho(f'\t{o_cat:15s} | {film:15s} | {nominees}', fg='yellow')
        if new_i:
            click.secho('IMDB Noms not matched:', fg='yellow')
            for nom_id, i_nom in new_i.items():
                film = ', '.join(v for (k, v) in i_nom.items() if 'tt' in k and v)
                nominees = ', '.join(v for (k, v) in i_nom.items() if 'tt' not in k)
                s = yaml.dump(i_nom, default_flow_style=True).strip()
                click.secho(f'\t{nom_id}: {s}', fg='yellow')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('years', nargs='*')
    parser.add_argument('-c', '--category-matching', action='store_true')
    parser.add_argument('-m', '--mode')
    parser.add_argument('-s', '--scitech', action='store_true')
    parser.add_argument('-k', '--core', action='store_true')
    parser.add_argument('-w', '--write', action='store_true')
    args = parser.parse_args()

    # Parse the list of years (if any)
    years = []
    for s in args.years:
        if '-' in s:
            a, _, b = s.partition('-')
            years += list(range(int(a), int(b) + 1))
        else:
            years.append(int(s))
    if args.years and 1933 in years:
        years.remove(1933)

    # Sort Oscar Nominations by Year
    oscars = read_csv()
    OSCARS = {}
    for nom in oscars:
        year = int(nom['Year'].split('/')[0])
        if year not in years:
            if not args.years:
                years.append(year)
            else:
                continue

        if year not in OSCARS:
            OSCARS[year] = {}
        cat = nom.get('CanonicalCategory', '')
        if cat not in OSCARS[year]:
            OSCARS[year][cat] = []
        OSCARS[year][cat].append(nom)

    # Read IMDb Data
    imdb_data = {}
    imdb_data_path = pathlib.Path('imdb_data')
    for year in years:
        imdb_year_path = imdb_data_path / f'{year}.yaml'
        if not imdb_year_path.exists():
            click.secho(f'Cannot find imdb yaml for {year}', fg='red')
            continue

        imdb_data[year] = yaml.safe_load(open(imdb_year_path))

    # Correct IMDB Data
    def recursive_update(d, u):
        for k, v in u.items():
            if isinstance(v, collections.abc.Mapping):
                d[k] = recursive_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d
    recursive_update(imdb_data, yaml.safe_load(open('aux_data/imdb_corrections.yaml')))

    # Match IMDb data with oscars data
    for year in years:
        click.secho(f'{year}=====', fg='blue', bg='white')
        match_year(OSCARS[year], imdb_data[year])

    # Gather Statistics about the total counts
    denominators = collections.Counter()

    for year in years:
        for cat, noms in OSCARS[year].items():
            denominators['Categories'] += 1
            for nom in noms:
                denominators['Nominations'] += 1
                if nom['Film']:
                    denominators['Films'] += 1
                denominators['Nominees'] += len(list(get_nominees(nom)))
                if nom['CanonicalCategory'] == 'MUSIC (Original Song)':
                    denominators['Songs'] += 1

    if args.write:
        write_csv(oscars)

    if args.write and not args.years:
        f = open('stats.txt', 'w')
    else:
        f = None

    print()
    for name, stat_dict, cats in [('Nominations', NOM_STATS, [('matched', 'green'),
                                                              ('extra_o', 'yellow'),
                                                              ('extra_i', 'yellow')]),
                                  ('Categories', CATEGORY_STATS, [('exact', 'green'),
                                                                  ('fuzzy', 'blue'),
                                                                  ('extra_o', 'yellow'),
                                                                  ('extra_i', 'yellow')]),
                                  ('Films', FILM_STATS, [('matched', 'green'),
                                                         ('unmatched', 'yellow'),
                                                         ('misses', 'red')]),
                                  ('Nominees', NOMINEE_STATS, [('matched', 'green'),
                                                               ('mismatched', 'red'),
                                                               ('extra_o', 'yellow'),
                                                               ('extra_i', 'yellow'),
                                                               ('misses', 'magenta'),
                                                               ]),
                                  ('Songs', SONG_STATS, [('matched', 'green'),
                                                         ('unmatched', 'yellow')])]:
        t_line = name + '=' * (38 - len(name))
        click.secho(t_line, bold=True)
        if f:
            f.write(t_line + '\n')
        total = denominators[name]
        if total == 0:
            total = 1
        for key, color in cats:
            c = stat_dict[key]
            s = f'{c:05d} {key:24s}| {c * 100 / total:6.2f}'
            click.secho(s, fg=color)
            if f:
                f.write(s + '\n')
        s = f'{total:05d} total'
        click.secho(s)
        if f:
            f.write(s + '\n')
    if f:
        f.close()

    if args.mode and 'names' in args.mode:
        for k, v in NAME_MISSES.most_common():
            if v == 1:
                continue
            click.secho(f'{v:03d} {k}', bg='blue')
