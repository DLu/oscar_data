#!/usr/bin/python3
import argparse
import re
import click
from tqdm import tqdm

from utilities import find_all_by_class, find_by_class, remove_enclosing, write_csv, BeautifulParser

ORDINAL = r'(\d+)(th|st|nd|rd)'
ORD_TAIL = r'\s+\(' + ORDINAL + r'\)'
YEAR_PATT = re.compile(r'(\d{4})' + ORD_TAIL)
YEAR_PATT2 = re.compile(r'(\d{4}/\d{2})' + ORD_TAIL)
TITLE_PATT = re.compile(r'The ' + ORDINAL + r' Academy Awards\s+\| (\d{4})')

SPECIAL_PARSE = [
    re.compile(r'^(?P<Name>[^-]+) -- (?P<Film>.*) \{"(?P<Detail>.*)"\}'),
    re.compile(r'^(?P<Film>[^-]+) -- (?P<Name>.*)')
]


NOTABLE_FIELDS = {
    'awardcategory-exact': 'Category',
    'nominationstatement': 'Name',
    'character': 'Detail',
    'songtitle': 'Detail',
    'publicnote': 'Note',
    'placement': 'Note',
    'citation': 'Citation',
    'dancenumber': 'Detail',
    'film-title': 'Film',
    'description': 'Note',
    'technical': 'Detail'
}


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

    if not award_info:
        for special_pattern in SPECIAL_PARSE:
            m = special_pattern.match(div_text)
            if m:
                award_info = m.groupdict()
                click.secho('Special Parse!', bg='cyan')
                for k, v in award_info.items():
                    click.secho(f'\t{k:10s}: ', fg='cyan', nl=False)
                    click.secho(v, fg='bright_cyan')
                break
        else:
            click.secho(f'Canont parse: {div_text}', fg='red')

    return award_info


def parse_awards(filepath):
    html = BeautifulParser(open(filepath))
    bar = tqdm(html.find_all_by_class('div', 'awards-result-chron'))
    for row in bar:
        header = find_by_class(row, 'div', 'result-group-header')
        year_text = header.text.strip()
        m = YEAR_PATT.match(year_text) or YEAR_PATT2.match(year_text)
        if not m:
            click.secho(f'Cannot parse year text: "{year_text}"', fg='red')
            exit(-1)
        year = m.group(1)
        bar.set_description(year)
        ceremony = int(m.group(2))

        for category_div in find_all_by_class(row, 'div', 'result-subgroup'):
            category = clean_string(find_by_class(category_div, 'div', 'result-subgroup-title').text.strip())

            category_dict = {'Category': category, 'Year': year, 'Ceremony': ceremony}

            for award_html in find_all_by_class(category_div, 'div', 'result-details'):
                award_info = parse_award(award_html)
                award_info.update(category_dict)

                yield award_info


SONG_PATTERN = re.compile(r'from ([^;]+); (.*)')

INTERNATIONAL_FIELDS = {
    'field--name-field-award-film': 'Name',
    'field--name-field-award-entities': 'Film'
}
OTHER_FIELDS = {
    'field--name-field-award-film': 'Film',
    'field--name-field-award-entities': 'Name',
}


def parse_nominations(filepath):
    html = BeautifulParser(open(filepath))

    title = html.find_by_class('div', 'field--name-title').text.strip()
    m = TITLE_PATT.search(title)
    ceremony = int(m.group(1))
    year = int(m.group(3)) - 1

    for row in html.find_all_by_class('div', 'paragraph--type--award-category'):
        cat_head = find_by_class(row, 'div', 'field--name-field-award-category-oscars')
        if not cat_head:
            continue
        category = cat_head.text
        FIELDS = INTERNATIONAL_FIELDS if category == 'International Feature Film' else OTHER_FIELDS
        for nom_el in find_all_by_class(row, 'div', 'paragraph--type--award-honoree'):
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
                        if cls == 'field--name-field-award-film':
                            cat = 'Detail'
                        else:
                            m = SONG_PATTERN.match(div_text)
                            add_value(nomination, 'Film', m.group(1))
                            add_value(nomination, 'Name', m.group(2))
                            continue
                    add_value(nomination, cat, div_text)

            yield nomination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--parse-nominations', action='store_true')
    args = parser.parse_args()

    awards = list(parse_awards('oscars_html/search_results.html'))

    if args.parse_nominations:
        awards += parse_nominations('oscars_html/nominations.html')

    write_csv(awards)
