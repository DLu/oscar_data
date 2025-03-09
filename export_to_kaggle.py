#!/usr/bin/python3
from utilities import read_csv
import csv

FIELD_LOOKUP = {
    'Ceremony': 'ceremony',
    'Category': 'category',
    'Film': 'film',
    'CanonicalCategory': 'canon_category',
    # 'Name': 'name',

}


if __name__ == '__main__':
    k_noms = []

    for nom in read_csv():

        if nom['Class'] == 'SciTech':
            continue

        k_nom = {}
        for k, v in FIELD_LOOKUP.items():
            k_nom[v] = nom[k]
        k_nom['name'] = '/'.join(nom['Nominees'].split(', '))

        if not k_nom['name'] and nom['Class'] == 'Special':
            s = nom['Citation']
            if s.startswith('To '):
                s = s[3:]
            k_nom['name'] = s.strip()

        if not k_nom['name']:
            k_nom['name'] = nom['Name']

        k_nom['winner'] = 'True' if nom['Winner'] else 'False'

        base_year = int(nom['Year'].split('/')[0])
        k_nom['year_film'] = base_year
        k_nom['year_ceremony'] = base_year + 1
        k_noms.append(k_nom)

    #
    #1927,1928,1,ACTOR,Richard Barthelmess,The Noose,False
    # {'CanonicalCategory': 'ACTOR IN A LEADING ROLE', }

    FIELDNAMES = ['year_film', 'year_ceremony', 'ceremony', 'category', 'canon_category', 'name', 'film', 'winner']
    outpath = 'the_oscar_award2.csv'
    with open(outpath, 'w') as f:
        writer = csv.DictWriter(f, FIELDNAMES)
        writer.writeheader()
        for row in k_noms:
            writer.writerow(row)
