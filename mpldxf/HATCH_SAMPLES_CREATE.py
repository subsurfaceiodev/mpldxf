from itertools import pairwise

import ezdxf
import pandas as pd
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
data.to_pickle('HATCH_SAMPLES.pickle')
