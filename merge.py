#!/usr/bin/python3
import argparse
import collections
import pathlib
import click
import unidecode
import re
import yaml

from utilities import read_csv, write_csv

PAREN_PATTERN = re.compile(r'^(.*) \((.*)\)$')
COLON_PATTERN = re.compile(r'^(.*): (.*)$')

SUFFIXES = yaml.safe_load(open('aux_data/suffixes.yaml'))
FIRST_NAMES = yaml.safe_load(open('aux_data/first_names.yaml'))
REMAP = yaml.safe_load(open('aux_data/hardcode.yaml'))

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
    if entry.get('Nominee(s)', '') == '':
        return
    names = entry['Nominee(s)'].split(', ')
    for name in names:
        for prefix in ['sir', 'dame']:
            if name.startswith(prefix):
                name = name = name[len(prefix):]
        if clean:
            yield get_nabble(name)
        else:
            yield name


def get_matching_category(category, options):
    lower_lookup = {get_nabble(a).replace('oftheyear', ''): a for a in options}
    category = get_nabble(category)

    for prefix in ['', 'best', 'bestachievementin', 'bestperformancebyan']:
        alt = prefix + category
        if alt in lower_lookup:
            return lower_lookup[alt]


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


def update_entry(o_nom, nom_id, i_nom, speculative=False):
    updates = {'NomId': nom_id}
    titles = [a for a in i_nom if 'tt' in a]
    if o_nom.get('Film'):
        if len(titles) == 1:
            updates['FilmId'] = titles[0]
            if not speculative:
                FILM_STATS['matched'] += 1
            titles = []
        elif not speculative:
            click.secho(f'Unable to match film for {o_nom["Category"]}', fg='yellow')
            FILM_STATS['unmatched'] += len(titles)
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
    for nom_name in get_nominees(o_nom, clean=False):
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

    updates['NomineeIds'] = ','.join(nom_ids.get(nom_name, '?') for nom_name in get_nominees(o_nom, clean=False))
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

    if should_print:
        film = o_nom.get('Film', '[NO FILM]')
        category = o_nom['Canonical Category']
        click.secho(f'{film} {category}', fg='red')
        if len(people) == 1 and len(unmatched_names) == 1:
            p_name, p_id = list(people.items())[0]
            click.secho(f'\t{nom_id}: {{{p_id}: {unmatched_names[0]}}}  # {p_name}', fg='red')
        else:
            click.secho(f'\t{nom_id}: {people} {unmatched_names}', fg='red')

    return valid


def match_categories(o_noms, i_noms, speculative=False):
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
        if o_nom.get('Canonical Category') == 'MUSIC (Original Song)':
            song_name = get_nabble(o_nom['Detail'])
            if song_name in song_lookup:
                nom_id = song_lookup[song_name]
                del song_lookup[song_name]
                i_unmatched.remove(nom_id)
                SONG_STATS['matched'] += 1
                update_entry(o_nom, nom_id, i_noms[nom_id], speculative=speculative)
            elif not speculative:
                if args.mode is None or args.mode == 'songs':
                    click.secho(f"Song doesn't match: {o_nom['Detail']} {song_name}", fg='red')
                    click.secho(f'\t{song_lookup}', fg='red')
                SONG_STATS['unmatched'] += 1
                o_unmatched.append(o_nom)
            else:
                o_unmatched.append(o_nom)
            continue

        # Non-Song Matching
        matching_name = None
        if o_nom.get('Film'):
            matching_name = get_matching_name(o_nom['Film'], names_to_noms, titles_match)

        if not matching_name:
            matching_name = get_matching_nominee(o_nom, names_to_noms)

        if matching_name:
            nom_id = names_to_noms[matching_name][0]
            if nom_id in i_unmatched and update_entry(o_nom, nom_id, i_noms[nom_id], speculative=speculative):
                i_unmatched.remove(nom_id)
                del names_to_noms[matching_name]
            continue

        if o_nom.get('Film') or o_nom.get('Nominee(s)'):
            o_unmatched.append(o_nom)

    o_matched_count = len(o_noms) - len(o_unmatched)
    if speculative:
        i_matched_count = len(i_noms) - len(i_unmatched)
        return (o_matched_count + i_matched_count) / (len(o_noms) + len(i_noms))
    else:
        NOM_STATS['matched'] += o_matched_count
        return o_unmatched, {nom_id: i_noms[nom_id] for nom_id in i_unmatched}


def match_years(oscars, imdb):
    unmatched_o_cats = set()
    unmatched_i_cats = set(imdb.keys())
    unmatched_o_noms = []
    unmatched_i_noms = {}

    for o_cat in oscars:
        i_cat = get_matching_category(o_cat, imdb)
        if i_cat not in imdb:
            unmatched_o_cats.add(o_cat)
            continue

        unmatched_i_cats.remove(i_cat)
        ou, iu, = match_categories(list(oscars[o_cat]), dict(imdb[i_cat]))
        unmatched_o_noms += ou
        unmatched_i_noms.update(iu)

    full_scores = []
    for o_cat in list(unmatched_o_cats):
        for i_cat in unmatched_i_cats:
            score = match_categories(list(oscars[o_cat]), dict(imdb[i_cat]), speculative=True)
            if score > 0.0:
                full_scores.append((score, o_cat, i_cat))

    for score, o_cat, i_cat in sorted(full_scores, reverse=True):
        if o_cat not in unmatched_o_cats or i_cat not in unmatched_i_cats:
            continue
        ou, iu, = match_categories(list(oscars[o_cat]), dict(imdb[i_cat]))
        unmatched_o_noms += ou
        unmatched_i_noms.update(iu)
        unmatched_o_cats.remove(o_cat)
        unmatched_i_cats.remove(i_cat)

    for o_cat in unmatched_o_cats:
        unmatched_o_noms += oscars[o_cat]

    for i_cat in unmatched_i_cats:
        unmatched_i_noms.update(imdb[i_cat])

    new_o, new_i = match_categories(unmatched_o_noms, unmatched_i_noms, speculative=False)
    NOM_STATS['extra_o'] += len(new_o)
    NOM_STATS['extra_i'] += len(new_i)

    for o_nom in new_o:
        NOMINEE_STATS['misses'] += len(list(get_nominees(o_nom)))

    if args.mode is None:
        if new_o:
            click.secho('Oscars Noms (unmatched):', fg='yellow')
            for o_nom in new_o:
                o_cat = o_nom['Canonical Category']
                film = o_nom.get('Film', '[x]')
                nominees = o_nom.get('Nominee(s)', '<>')
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
    parser.add_argument('-m', '--mode')
    parser.add_argument('-w', '--write', action='store_true')
    args = parser.parse_args()

    years = []
    for s in args.years:
        if '-' in s:
            a, _, b = s.partition('-')
            years += list(range(int(a), int(b) + 1))
        else:
            years.append(int(s))

    oscars = read_csv()
    OSCARS = {}
    for nom in oscars:
        year = int(nom['Year'].split('/')[0])
        if not args.years:
            years.append(year)
        elif year not in years:
            continue

        if year not in OSCARS:
            OSCARS[year] = {}
        cat = nom.get('Canonical Category', '')
        if cat not in OSCARS[year]:
            OSCARS[year][cat] = []
        OSCARS[year][cat].append(nom)

    # Remove years that don't actually have noms
    years = sorted(set(years).intersection(set(OSCARS.keys())))

    imdb_data_path = pathlib.Path('imdb_data')

    for year in years:
        if year not in OSCARS:
            continue

        imdb_year_path = imdb_data_path / f'{year}.yaml'
        if not imdb_year_path.exists():
            click.secho(f'Cannot find imdb yaml for {year}', fg='red')
            continue

        imdb_data = yaml.safe_load(open(imdb_year_path))

        click.secho(f'{year}=====', fg='blue', bg='white')
        match_years(OSCARS[year], imdb_data)

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
                                  ('Films', FILM_STATS, [('matched', 'green'),
                                                         ('unmatched', 'yellow')]),
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
        total = sum(stat_dict.values())
        if total == 0:
            total = 1
        for key, color in cats:
            c = stat_dict[key]
            s = f'{c:05d} {key:24s}| {c * 100 / total:6.2f}'
            click.secho(s, fg=color)
            if f:
                f.write(s + '\n')
    if f:
        f.close()

    if args.mode and 'names' in args.mode:
        for k, v in NAME_MISSES.most_common():
            if v == 1:
                continue
            click.secho(f'{v:03d} {k}', bg='blue')
