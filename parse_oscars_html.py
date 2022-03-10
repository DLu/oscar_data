#!/usr/bin/python3
import argparse
import re
import click

from beautiful_parser import is_comment, find_all_by_class, find_by_class, BeautifulParser
from utilities import write_csv

ORDINAL = r'(\d+)(th|st|nd|rd)'
ORD_TAIL = r'\s+\(' + ORDINAL + r'\)'
YEAR_PATT = re.compile(r'(\d{4})' + ORD_TAIL)
YEAR_PATT2 = re.compile(r'(\d{4}/\d{2})' + ORD_TAIL)
TITLE_PATT = re.compile(r'The ' + ORDINAL + r' Academy Awards \| (\d{4})')


NOTABLE_FIELDS = {
    'awardcategory-exact': 'Category',
    'nominationstatement': 'Name',
    'character': 'Detail',
    'songtitle': 'Detail',
    'publicnote': 'Note',
    'placement': 'Placement',
    'citation': 'Citation',
    'dancenumber': 'Detail',
    'film-title': 'Film',
    'description': 'Note',
    'technical': 'Detail'
}


def remove_enclosing(text, chars=['{}', '[]', '""']):
    match_dict = {s[0]: s[1] for s in chars}
    while text and text[0] in match_dict and match_dict[text[0]] == text[-1]:
        text = text[1:-1]
    return text


def clean_string(text):
    text = text.replace('\n', ' ')
    while '  ' in text:
        text = text.replace('  ', ' ')
    return text


def add_value(d, key, value):
    if key in d:
        if isinstance(d[key], str):
            d[key] = [d[key]]
        d[key].append(value)
    else:
        d[key] = value


def parse_award(award_html):
    award_info = {}
    award_info['Class'] = award_html.find(string=is_comment)
    if find_by_class(award_html, 'span', 'glyphicon-star'):
        award_info['Winner'] = True

    for div in award_html.find_all('div'):
        if isinstance(div, str):
            continue
        div_text = div.text.strip()
        if div_text and div_text[-1] == ';':
            div_text = div_text[:-1]
        div_text = clean_string(remove_enclosing(div_text))
        if not div_text:
            continue
        for cls in div['class']:
            cls = cls.replace('awards-result-', '')
            if cls not in NOTABLE_FIELDS:
                continue
            cat = NOTABLE_FIELDS[cls]

            add_value(award_info, cat, div_text)

    return award_info


def parse_awards(filepath):
    html = BeautifulParser(open(filepath))
    for row in html.find_all_by_class('div', 'awards-result-chron'):
        header = find_by_class(row, 'div', 'result-group-header')
        year_text = header.text.strip()
        m = YEAR_PATT.match(year_text) or YEAR_PATT2.match(year_text)
        if not m:
            click.secho(f'Cannot parse year text: "{year_text}"', fg='red')
            exit(-1)
        year = m.group(1)
        ceremony = int(m.group(2))

        for category_div in find_all_by_class(row, 'div', 'result-subgroup'):
            category = clean_string(find_by_class(category_div, 'div', 'result-subgroup-title').text.strip())

            category_dict = {'Category': category, 'Year': year, 'Ceremony': ceremony}

            for award_html in find_all_by_class(category_div, 'div', 'result-details'):
                award_info = parse_award(award_html)
                award_info.update(category_dict)

                # Split multifilm nominations
                if isinstance(award_info.get('Film'), list):
                    for i, film in enumerate(award_info['Film']):
                        new_row = {}
                        for k, v in award_info.items():
                            if isinstance(v, list) and k != 'Nominee(s)':
                                if i >= len(v):
                                    print(award_info)
                                    continue
                                new_row[k] = v[i]
                            else:
                                new_row[k] = v
                        new_row['MultifilmNomination'] = True
                        yield new_row
                else:
                    yield award_info


SONG_PATTERN = re.compile(r'from ([^;]+); (.*)')

ACTOR_FIELDS = {
    'title': 'Film',
    'field-actor-name': 'Name'
}
OTHER_FIELDS = {
    'title': 'Name',
    'field-actor-name': 'Film'
}


def parse_nominations(filepath):
    html = BeautifulParser(open(filepath))

    title = html.find_by_class('div', 'views-field-title').text.strip()
    m = TITLE_PATT.search(title)
    ceremony = int(m.group(1))
    year = int(m.group(3)) - 1

    for row in html.find_all_by_class('div', 'view-grouping'):
        category = row.find('h2').text
        FIELDS = ACTOR_FIELDS if ' in a ' in category else OTHER_FIELDS
        for nom_el in find_all_by_class(row, 'div', 'views-row'):
            nomination = {'Category': category, 'Ceremony': ceremony, 'Year': year}
            for div in nom_el.find_all('div'):
                if isinstance(div, str):
                    continue
                div_text = div.text.strip()
                if not div_text:
                    continue
                for cls in div['class']:
                    cls = cls.replace('views-field-', '')
                    if cls not in FIELDS:
                        continue
                    cat = FIELDS[cls]
                    if category == 'Music (Original Song)':
                        if cls == 'field-actor-name':
                            cat = 'Detail'
                        else:
                            m = SONG_PATTERN.match(div_text)
                            add_value(nomination, 'Film', m.group(1))
                            add_value(nomination, 'Name', m.group(2))
                            continue
                    add_value(nomination, cat, div_text)

            yield nomination


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
            if '  ' in v:
                print(k)
            new_entry[k] = v
        else:
            new_entry[k] = str(v)

    return new_entry


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--parse-nominations', action='store_true')
    args = parser.parse_args()

    awards = list(parse_awards('oscars_html/search_results.html'))

    if args.parse_nominations:
        awards += parse_nominations('oscars_html/nominations.html')

    write_csv(awards)