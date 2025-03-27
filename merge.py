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

FIRST_NAMES = yaml.safe_load(open('aux_data/first_names.yaml'))
SUFFIXES = yaml.safe_load(open('aux_data/suffixes.yaml'))
COMPANY_LOOKUP = read_lookup_dict('aux_data/companies.yaml')
COMPANY_CATEGORIES = {
    'BEST PICTURE', 'UNIQUE AND ARTISTIC PICTURE', 'SPECIAL AWARD', 'OUTSTANDING PRODUCTION',
    'SHORT SUBJECT (Comedy)', 'SHORT SUBJECT (Novelty)', 'SHORT SUBJECT (Color)', 'SHORT SUBJECT (One-reel)',
    'SHORT SUBJECT (Two-reel)', 'SHORT FILM (Animated)', 'SOUND RECORDING', 'SOUND', 'MUSIC (Scoring)',
    'SCIENTIFIC OR TECHNICAL AWARD (Class III)', 'SCIENTIFIC OR TECHNICAL AWARD (Class II)',
    'SCIENTIFIC OR TECHNICAL AWARD (Class I)', 'SPECIAL EFFECTS', 'DOCUMENTARY (Short Subject)',
    'DOCUMENTARY (Feature)',
}
NAME_ALIASES = read_lookup_dict('aux_data/name_aliases.yaml')
FILM_ALIASES = yaml.safe_load(open('aux_data/film_aliases.yaml'))
SONG_ALIASES = yaml.safe_load(open('aux_data/song_aliases.yaml'))
IMDB_CAT = yaml.safe_load(open('aux_data/imdb_cat_to_canon.yaml'))
MATCH_MODES = yaml.safe_load(open('aux_data/match_modes.yaml'))

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


def get_film_ids(nom):
    if not nom.get('FilmId'):
        return ['?'] * len(nom.get('Film').split('|'))

    if isinstance(nom['FilmId'], list):
        return nom['FilmId']
    else:
        return nom['FilmId'].split('|')


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


def get_matching_key(query, values_d, match_fn, aliases):
    if query in values_d:
        return query

    short = get_nabble(query)
    for key in values_d:
        if key in aliases:
            sk = get_nabble(aliases[key])
        elif not isinstance(values_d[key], dict) and values_d[key] in aliases:
            sk = get_nabble(aliases[values_d[key]])
        else:
            sk = get_nabble(key)
        if sk == short:
            return key

        if match_fn and match_fn(query, key):
            return key


def get_best_matching_key(nom_vals, i_noms_d, match_fn, aliases):
    if nom_vals in i_noms_d:
        return nom_vals

    best_key = None
    best_count = 0

    for nom_key, i_nom in sorted(i_noms_d.items()):
        match_count = 0
        for nom_name in nom_vals:
            if nom_name in aliases and aliases[nom_name] in i_nom:
                match_count += 1
                continue

            for nom_key_val in nom_key:
                if match_fn(nom_key_val, nom_name):
                    match_count += 1
                    break
        if match_count == 0:
            continue
        if best_key is None or best_count < match_count:
            best_key = nom_key
            best_count = match_count

    return best_key


def get_name_match(nom_name, people):
    if nom_name in people:
        return nom_name

    matches = []
    for i_name in people:
        if names_match(nom_name, i_name):
            matches.append(i_name)
    if len(matches) == 1:
        return matches[0]


def get_match_mode(o_nom):
    for match_mode in MATCH_MODES:
        for field, values in match_mode['criteria'].items():
            value = o_nom[field]
            if value not in values:
                break
        else:
            return match_mode['mode']


def match_nomination(o_nom, i_nom, match_mode, speculative=False):
    updates = {}
    if o_nom.get('Film'):
        o_titles = o_nom['Film'].split('|')
    else:
        o_titles = []
    i_titles = {title: key for key, title in i_nom.items() if key.startswith('tt')}

    if o_titles or i_titles:
        if len(o_titles) == 1 and len(i_titles) == 1:
            updates['FilmId'] = list(i_titles.values())[0]
            i_titles = {}
        elif not speculative:
            changed = True
            film_ids = ['?'] * len(o_titles)
            while changed:
                changed = False
                for oi, o_title in enumerate(o_titles):
                    if film_ids[oi] != '?':
                        continue

                    matching_key = get_matching_key(o_title, i_titles, titles_match, FILM_ALIASES)

                    if matching_key:
                        film_ids[oi] = i_titles[matching_key]
                        del i_titles[matching_key]
                        changed = True

            if match_mode != 'multi' and (i_titles or '?' in film_ids):
                if not speculative:
                    click.secho(f'Unable to match film for {o_nom['CanonicalCategory']}', fg='yellow')
                    if args.mode is None or args.mode == 'missing_film_names':
                        for film_id, o_title in zip(film_ids, o_titles):
                            if film_id == '?':
                                click.secho(f'Missing Film Name: {o_title}', fg='red')

            updates['FilmId'] = film_ids

        elif not speculative:
            click.secho(f'Unable to match film for {o_nom['Category']}', fg='yellow')
            if args.mode is None or args.mode == 'missing_film_names':
                click.secho(f'Missing Film Name: {o_nom["Film"]}', fg='red')

    people = {}
    for k, v in i_nom.items():
        if k.startswith('tt') or k == 'song' or v is None:
            continue
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

    def remove_match(imdb_id):
        matching_names = [k for k in people if people[k] == n_id]
        if len(matching_names) == 1:
            matching_name = matching_names[0]
            del people[matching_name]
            return True

    for nom_name in nom_names:
        if nom_name in nom_ids:
            remove_match(nom_ids[nom_name])
            continue
        if canon_category in COMPANY_CATEGORIES and nom_name in COMPANY_LOOKUP:
            nom_ids[nom_name] = COMPANY_LOOKUP[nom_name]
            people.pop(nom_name, None)
            continue
        if nom_name in NAME_ALIASES:
            n_id = NAME_ALIASES[nom_name]
            if remove_match(n_id):
                nom_ids[nom_name] = n_id
                continue

        matching_name = get_name_match(nom_name, people)
        if matching_name:
            nom_ids[nom_name] = people[matching_name]
            del people[matching_name]
            continue
        unmatched_names.append(nom_name)

    valid = nom_ids or original_people_count == 0

    if speculative:
        return valid

    if not valid:
        return valid

    updates['NomineeIds'] = [nom_ids.get(nom_name, '?') for nom_name in nom_names]
    o_nom.update(updates)

    if o_nom['Film']:
        films = o_nom['Film'].split('|')
        for film, film_id in zip(films, get_film_ids(o_nom)):
            if film_id == '?':
                FILM_STATS['unmatched'] += 1
            else:
                FILM_STATS['matched'] += 1

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
        for film_id in get_film_ids(o_nom):
            click.secho(f'\thttp://imdb.com/title/{film_id}/fullcredits', fg='red')
        if len(people) == 1 and len(unmatched_names) == 1:
            p_name, p_id = list(people.items())[0]
            click.secho(f'\t{{{p_id}: {unmatched_names[0]}}}  # {p_name}', fg='red')
        elif unmatched_names and not people:
            for name in unmatched_names:
                click.secho(f'\tUnmatched Nominee: {name}', fg='red')
            if len(unmatched_names) != 1 or unmatched_names[0] != o_nom['Name']:
                full = o_nom['Name'] or o_nom['Nominees']
                click.secho(f'\tFull: {full}', fg='bright_red')
        elif people and not unmatched_names:
            for name in people:
                click.secho(f'\tExtra IMDb Nominee: {name}', fg='red')
        else:
            click.secho(f'\t{people} {unmatched_names}', fg='red')

    return valid


def match_category(o_noms, i_noms, match_mode, speculative=False):
    i_noms_d = {}
    i_noms_c = collections.Counter()  # For handling multiple noms per key
    # Mostly just applies to IVAN KRUGLAK
    i_unmatched = []

    for nom in i_noms:
        if match_mode == 'film':
            values = [FILM_ALIASES.get(k, v) for (k, v) in nom.items() if k.startswith('tt')]
            nom_key = tuple(values)
        elif match_mode == 'song':
            nom_key = nom['song']
        elif match_mode in ['nominee', 'multi', 'nominee+']:
            nom_key = tuple([v for (k, v) in nom.items() if not k.startswith('tt')])
        else:
            raise RuntimeError(f'Unknown match mode {match_mode}')

        if nom_key is None or nom_key == tuple():
            i_unmatched.append(nom)
            continue

        if nom_key in i_noms_d:
            i_noms_d[nom_key].update(nom)
        else:
            i_noms_d[nom_key] = nom
        i_noms_c[nom_key] += 1

    o_unmatched = []

    for o_nom in o_noms:
        if match_mode in ['nominee', 'multi', 'nominee+']:
            nom_vals = tuple(get_nominees(o_nom, clean=False))
            matching_key = get_best_matching_key(nom_vals, i_noms_d, names_match, NAME_ALIASES)
        elif match_mode == 'film':
            nom_vals = tuple(o_nom['Film'].split('|'))
            matching_key = get_best_matching_key(nom_vals, i_noms_d, titles_match, FILM_ALIASES)
        elif match_mode == 'song':
            nom_val = o_nom['Detail']
            matching_key = get_matching_key(nom_val, i_noms_d, None, SONG_ALIASES)

        if matching_key:
            match_nomination(o_nom, i_noms_d[matching_key], match_mode, speculative=speculative)
            # check if returns true?
            i_noms_c[matching_key] -= 1

            if match_mode == 'multi' and o_nom['FilmId']:
                for film_id in get_film_ids(o_nom):
                    if film_id != '?':
                        i_noms_d[matching_key].pop(film_id)

                if len(i_noms_d[matching_key]) == 1:
                    del i_noms_d[matching_key]

            elif i_noms_c[matching_key] == 0 or match_mode != 'nominee+':
                del i_noms_d[matching_key]

            if match_mode == 'song' and not speculative:
                SONG_STATS['matched'] += 1
        else:
            o_unmatched.append(o_nom)
            if not speculative:
                if match_mode == 'song':
                    SONG_STATS['unmatched'] += 1
                    if args.mode is None or args.mode == 'songs':
                        click.secho(f"Song doesn't match: {nom_val}", fg='red')
                        for nom_song in i_noms_d.keys():
                            click.secho(f'\t{nom_song}', fg='red')

    o_matched_count = len(o_noms) - len(o_unmatched)
    if speculative:
        i_matched_count = len(i_noms) - len(i_noms_d)
        return (o_matched_count + i_matched_count) / (len(o_noms) + len(i_noms))
    else:
        NOM_STATS['matched'] += o_matched_count
        return o_unmatched, i_unmatched + list(i_noms_d.values())


def match_year(oscars, imdb):
    unmatched_o_cats = set()
    unmatched_i_cats = set(imdb.keys())
    unmatched_o_noms = []
    unmatched_i_noms = []

    def get_matching_category(category, options):
        icats = set(IMDB_CAT.get(category, []))
        fcats = set(options.keys())
        m = icats.intersection(fcats)
        if m:
            assert len(m) == 1
            return list(m)[0]

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
            if args.category_matching:
                click.secho(f'No category match:        {o_cat:40s} ', bg='yellow', fg='black')
            continue

        unmatched_i_cats.remove(i_cat)
        if args.category_matching:
            click.secho(f'Exact category match:     {o_cat:40s} {i_cat:40s}', bg='green')
        CATEGORY_STATS['exact'] += 1
        match_mode = get_match_mode(oscars[o_cat][0])
        ou, iu, = match_category(list(oscars[o_cat]), list(imdb[i_cat]), match_mode)
        unmatched_o_noms += ou
        unmatched_i_noms += iu

    full_scores = []
    for o_cat in list(unmatched_o_cats):
        for i_cat in unmatched_i_cats:
            match_mode = get_match_mode(oscars[o_cat][0])
            score = match_category(list(oscars[o_cat]), list(imdb[i_cat]), match_mode, speculative=True)
            if score > 0.0:
                full_scores.append((score, o_cat, i_cat))

    for score, o_cat, i_cat in sorted(full_scores, reverse=True):
        if o_cat not in unmatched_o_cats or i_cat not in unmatched_i_cats:
            continue
        if args.category_matching:
            click.secho(f'Fuzzy Category Match: {score:.1f} {o_cat:40s} {i_cat:40s}', bg='blue')
        CATEGORY_STATS['fuzzy'] += 1

        match_mode = get_match_mode(oscars[o_cat][0])
        ou, iu, = match_category(list(oscars[o_cat]), list(imdb[i_cat]), match_mode)
        unmatched_o_noms += ou
        unmatched_i_noms += iu
        unmatched_o_cats.remove(o_cat)
        unmatched_i_cats.remove(i_cat)

    for o_cat in unmatched_o_cats:
        CATEGORY_STATS['extra_o'] += 1
        unmatched_o_noms += oscars[o_cat]

    for i_cat in unmatched_i_cats:
        CATEGORY_STATS['extra_i'] += 1
        unmatched_i_noms += imdb[i_cat]

    if args.category_matching:
        click.secho('Leftovers!', bg='blue')
    if unmatched_o_noms and unmatched_i_noms:
        new_o0, new_i0 = match_category(unmatched_o_noms, unmatched_i_noms, 'nominee', speculative=False)
        new_o, new_i = match_category(new_o0, new_i0, 'film', speculative=False)
    else:
        new_o = unmatched_o_noms
        new_i = unmatched_i_noms
    NOM_STATS['extra_o'] += len(new_o)
    NOM_STATS['extra_i'] += len(new_i)

    for o_nom in new_o:
        if o_nom['Film']:
            FILM_STATS['misses'] += 1
            if args.mode is None or args.mode == 'film_misses':
                click.secho(f"Unknown film: {o_nom['Film']}", bg='red')
        for nominee in get_nominees(o_nom, False):
            NOMINEE_STATS['misses'] += 1
            if o_nom['Class'] == 'SciTech' and not args.scitech:
                continue
            if args.mode is None or args.mode == 'nominee_misses':
                click.secho(f"Unknown nominee: {nominee}", bg='red')

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
            for i_nom in new_i:
                film = ', '.join(v for (k, v) in i_nom.items() if 'tt' in k and v)
                nominees = ', '.join(v for (k, v) in i_nom.items() if 'tt' not in k)
                s = yaml.dump(i_nom, default_flow_style=True, allow_unicode=True).strip()
                click.secho(f'\t{s}', fg='yellow')


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
    cnums = {}
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

        cnums[year] = int(nom['Ceremony'])

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
    for year, cats in yaml.safe_load(open('aux_data/supplemental_imdb_data.yaml')).items():
        if year not in imdb_data:
            continue
        awards = imdb_data[year]['awards']
        for cat, updates in cats.items():
            if updates is None:
                # Remove category entirely
                awards.pop(cat)
                continue

            elif isinstance(updates, str):
                if updates == 'split':
                    # Split imdb nomination into individuals
                    entities = awards[cat]
                    awards[cat] = []
                    for entity in entities:
                        for k, v in entity.items():
                            awards[cat].append({k: v})
                else:
                    assert updates == 'merge'
                    # Merge all imdb nominations for this cat into one
                    main = {}
                    entities = awards[cat]
                    awards[cat] = [main]
                    for entity in entities:
                        main.update(entity)

                continue
            if cat not in awards:
                awards[cat] = []
            for i_nom in list(awards[cat]):
                overlap = set(updates.keys()).intersection(i_nom.keys())
                if overlap:
                    assert len(overlap) == 1
                    key = list(overlap)[0]
                    if updates[key] is None:
                        # Remove nomination entirely
                        awards[cat].remove(i_nom)
                    else:
                        # Update/remove values from nom
                        for k, v in updates[key].items():
                            if not v:
                                del i_nom[k]
                            else:
                                i_nom[k] = v
                    del updates[key]

            for update in updates.values():
                awards[cat].append(update)

    # Match IMDb data with oscars data
    try:
        for year in years:
            click.secho(f'#{cnums[year]}) {year}', fg='blue', bg='white')
            match_year(OSCARS[year], imdb_data[year]['awards'])
    except click.Abort:
        pass

    # Gather Statistics about the total counts
    denominators = collections.Counter()

    for year in years:
        for cat, noms in OSCARS[year].items():
            denominators['Categories'] += 1
            for nom in noms:
                denominators['Nominations'] += 1
                if nom['Film']:
                    denominators['Films'] += len(nom['Film'].split('|'))
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
