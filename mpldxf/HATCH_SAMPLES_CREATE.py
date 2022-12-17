from itertools import pairwise

import ezdxf
import pandas as pd
from subsurfaceio import data_path
from subsurfaceio.dxf.functions import read_entities

doc = ezdxf.readfile('HATCH SAMPLES.dxf')
msp = doc.modelspace()

data = {}

for insert in msp.query('INSERT'):

    name = insert.dxf.name
    if name == '*U2': continue
    block_obj = doc.blocks[name]
    data[name] = pd.DataFrame(read_entities(block_obj))

data = pd.concat(data, names=['name', '#'])
data.reset_index(level=1, inplace=True)
data['#'] += 1
data_ = data
# data.to_pickle('HATCH_SAMPLES.pickle')

from collections import defaultdict
data = {}
df = pd.read_pickle(f'{data_path}/build_hatches.pickle')
for (name, path_id), df_ in df.groupby(df.index, sort=False):
    path_id_i = 0
    for (i0, r0), (i1, r1) in pairwise(df_.iterrows()):
        data[(name, f'{path_id}.{path_id_i}')] = {'x0': r0['x'], 'y0': r0['y'], 'x1': r1['x'], 'y1': r1['y']}
        path_id_i += 1
data = pd.DataFrame.from_dict(data, orient='index')
data.index.names = ['name', '#']
data.reset_index(level=1, inplace=True)
data = pd.concat([data_, data])
print(data)
# data['#'] += 1
data.to_pickle('HATCH_SAMPLES.pickle', compression='gzip')