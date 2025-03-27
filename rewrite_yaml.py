import pathlib
import yaml

for filepath in pathlib.Path('aux_data').glob('*.yaml'):
    if filepath.stem in ['canonical', 'classes']:
        continue
    data = yaml.safe_load(open(filepath))
    yaml.safe_dump(data, open(filepath, 'w'), allow_unicode=True)
