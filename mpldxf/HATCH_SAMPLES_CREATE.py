from itertools import pairwise

import ezdxf
import pandas as pd

doc = ezdxf.readfile('HATCH SAMPLES.dxf')
msp = doc.modelspace()

data = {}

for insert in msp.query('INSERT'):
    def update_data():
        data[(name, ei + 1)] = {'x0': start[0], 'y0': start[1], 'x1': end[0], 'y1': end[1]}


    name = insert.dxf.name
    if name == '*U2': continue
    block_obj = doc.blocks[name]
    ei = 1
    for e in block_obj:
        if e.dxftype() in ['LINE']:
            start, end = e.dxf.start, e.dxf.end
            update_data()
            ei += 1
        elif e.dxftype() in ['CIRCLE', 'ARC']:
            Vec3 = e.flattening(sagitta=0.001)
            for start, end in pairwise(Vec3):
                update_data()
                ei += 1
data = pd.DataFrame.from_dict(data, orient='index')
data.index.names = ['name', '#']
data.reset_index(level=1, inplace=True)
data.to_pickle('HATCH_SAMPLES.pickle')
