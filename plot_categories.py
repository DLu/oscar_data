from utilities import read_csv
import collections
import argparse
import click

parser = argparse.ArgumentParser()
parser.add_argument('award_class')
args = parser.parse_args()


def super_sum(dd):
    return sum(len(v) for v in dd.values())


def condense_list(values):
    s_values = []
    start = None
    end = None
    for value in sorted(values):
        if start is None:
            start = value
            end = value
        elif value == end + 1:
            end = value
        elif start == end:
            s_values.append(str(start))
            start = value
            end = value
        else:
            s_values.append(f'{start}-{end}')
            start = value
            end = value

    if start == end:
        s_values.append(str(start))
    else:
        s_values.append(f'{start}-{end}')
        start = value
        end = value

    return ' '.join(s_values)


ceremonies = collections.defaultdict(lambda: collections.defaultdict(set))
max_c = 0

for nom in read_csv():
    if nom['Class'] != args.award_class:
        continue
    ceremony = int(nom['Ceremony'])
    max_c = max(max_c, ceremony)
    canon = nom['CanonicalCategory']
    base = nom['Category']

    ceremonies[canon][base].add(ceremony)


def header():
    for i in range(0, max_c + 1):
        if i == 0:
            click.secho(' ', nl=False)
        elif i % 10 == 0:
            click.secho(str(i // 10), fg='bright_white', nl=False)
        else:
            click.secho('.', nl=False)
    print()


for canon, cerem in sorted(ceremonies.items(), key=lambda pair: super_sum(pair[1]), reverse=True):
    s = f'Canonical: {canon}'
    s += ' ' * (max_c - len(s) + 1)
    click.secho(s, bg='blue', fg='bright_white')
    header()
    count = collections.Counter()
    for cat, a in cerem.items():
        for i in a:
            count[i] += 1
    if len(cerem) > 1:
        for i in range(0, 99):
            if count[i] == 1:
                click.secho(' ', bg='green', nl=False)
            elif count[i] == 0:
                click.secho(' ', nl=False)
            else:
                click.secho(' ', bg='red', nl=False)
        print()

    for cat, a in sorted(cerem.items(), key=lambda d: min(d[1])):
        cs = [' '] * min(a) + list(cat)
        cs += [' '] * (100 - len(cs))
        colors = ['black'] * len(cs)
        for i in a:
            if count[i] > 1:
                colors[i] = 'red'
            else:
                colors[i] = 'white'
        for c, color in zip(cs, colors):
            if color == 'black':
                click.secho(c, bg=color, fg='white', nl=False)
            else:
                click.secho(c, bg=color, fg='black', nl=False)
        print(condense_list(a))
        print()
    print()
