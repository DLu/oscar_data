from utilities import read_csv
import argparse
import collections
import numpy
from matplotlib.pyplot import subplots, show
from merge import get_nominees, get_film_ids

parser = argparse.ArgumentParser()
parser.add_argument('-t', '--sci-tech', action='store_true')
parser.add_argument('-s', '--special', action='store_true')
parser.add_argument('-r', '--relative', action='store_true')
args = parser.parse_args()

data = collections.defaultdict(  # First key is Stat-Type
    lambda: collections.defaultdict(  # second key is Ceremony
        collections.Counter  # third key is classification
    )
)
classifications = collections.defaultdict(set)

ordering = ['perfect', 'matched', 'unmatched', 'missed']
colors = {
    'perfect': 'blue',
    'matched': 'green',
    'unmatched': 'magenta',
    'missed': 'red',
}

prev_c = None
xticks = []
xlabels = []

for nom in read_csv():
    if not args.sci_tech and nom['Class'] == 'SciTech':
        continue
    if not args.special and nom['Class'] == 'Special':
        continue

    nom_matched = False
    c = int(nom['Ceremony'])

    if c != prev_c:
        if nom['Year'][-1] == '0':
            xlabels.append('{Year}\n#{Ceremony}'.format(**nom))
            xticks.append(c)
        elif nom['Year'][-1] == '5':
            xlabels.append('')
            xticks.append(c)
    prev_c = c

    def mark(stat, cls, n=1):
        data[stat][c][cls] += 1
        classifications[stat].add(cls)

    nom_count = len(list(get_nominees(nom, False)))
    if nom_count:
        if nom['NomineeIds'] == '':
            mark('Nominees', 'missed', nom_count)
        else:
            for nom_id in nom['NomineeIds'].split('|'):
                if nom_id == '?':
                    mark('Nominees', 'unmatched')
                else:
                    mark('Nominees', 'matched')
                    nom_matched = True

    if nom['Film']:
        film_ids = get_film_ids(nom)
        for film_id in film_ids:
            if film_id == '?':
                mark('Films', 'unmatched')
            else:
                mark('Films', 'matched')
                nom_matched = True

    if nom_matched:
        mark('Nominations', 'matched')
    else:
        mark('Nominations', 'unmatched')


f, axes = subplots(len(data))
for ax, stat_name in zip(axes.flat, data.keys()):
    ax.set_title(stat_name)
    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels)
    ceremonies = sorted(data[stat_name].keys())

    for c in ceremonies:
        n = data[stat_name][c]['matched']
        t = sum(data[stat_name][c].values())
        if n == t:
            data[stat_name][c]['matched'] = 0
            data[stat_name][c]['perfect'] = n
            classifications[stat_name].add('perfect')

    prev = numpy.array([0.0] * len(ceremonies))
    for classification in sorted(classifications[stat_name],
                                 key=lambda cls: ordering.index(cls)
                                 if cls in ordering else len(ordering)
                                 ):
        y = []
        for ceremony in ceremonies:
            if args.relative:
                y.append(data[stat_name][ceremony][classification] * 100 / sum(data[stat_name][ceremony].values()))
            else:
                y.append(data[stat_name][ceremony][classification])
        ax.bar(ceremonies, y, bottom=prev, label=classification, color=colors.get(classification, 'black'))
        prev += numpy.array(y)
    ax.legend()
show()
