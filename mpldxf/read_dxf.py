import ezdxf
from mpldxf.HatchMakerSSIO import hatchmaker
from itertools import pairwise
doc = ezdxf.readfile('dxf sample.dxf')
msp = doc.modelspace()


for e in msp:
    if e.dxftype() in ['LINE']:
        start = e.dxf.start
        end = e.dxf.end
        print(hatchmaker(p0=(start[0], start[1]), p1=(end[0], end[1]), return_as_string=True))
    elif e.dxftype() in ['CIRCLE', 'ARC']:
        Vec3 = e.flattening(sagitta=0.001)
        for start, end in pairwise(Vec3):
            print(hatchmaker(p0=(start[0], start[1]), p1=(end[0], end[1]), return_as_string=True))