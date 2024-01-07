import numpy as np
from mpldxf.hatchmaker import HatchMaker
import pytest


def test_pattycake():
    expected = '''*test_pattycake,description
;angle,x,y,shift,offset,dash,space
90.000000,0.12500000,0.05000000,0.00000000,1.00000000,0.07500000,-0.92500000
45.000000,0.12500000,0.12500000,0.70710678,-0.70710678,0.12501648,-1.28919708
315.000000,0.03660000,0.21340000,0.70710678,-0.70710678,0.12501648,-1.28919708
90.000000,0.37500000,0.31790000,0.00000000,1.00000000,0.05710000,-0.94290000
45.000000,0.37500000,0.37500000,0.70710678,-0.70710678,0.12501648,-1.28919708
315.000000,0.28660000,0.46340000,0.70710678,-0.70710678,0.12501648,-1.28919708
'''
    hm = HatchMaker(
        pat_title='test_pattycake'
    ).set_from_points(
        [
            (0.125, 0.05),
            (0.125, 0.125),
            (0.0366, 0.2134),
            (0.375, 0.3179),
            (0.375, 0.375),
            (0.2866, 0.4634),
        ],
        [
            (0.125, 0.125),
            (0.2134, 0.2134),
            (0.125, 0.125),
            (0.375, 0.375),
            (0.4634, 0.4634),
            (0.375, 0.375),
        ],
    )
    hm.to_dxf()
    assert hm.to_pat_str() == expected


def test_single():
    # based on peat hatch at https://www.cadhatch.com/bs5930-geological-hatch
    expected = '''*test_single,description
;angle,x,y,shift,offset,dash,space
116.565051,0.11000000,0.00000000,-0.89442719,0.44721360,0.13416408,-2.10190390
105.945396,0.15000000,0.06000000,3.15929297,0.13736056,0.14560220,-7.13450769
90.000000,0.19000000,0.00000000,0.00000000,1.00000000,0.18000000,-0.82000000
74.054604,0.23000000,0.06000000,3.15929297,-0.13736056,0.14560220,-7.13450769
63.434949,0.27000000,0.00000000,-0.89442719,-0.44721360,0.13416408,-2.10190390
'''
    hm = HatchMaker(
        pat_title='test_single'
    ).set_from_points(
        [
            (0.11, 0.00),
            (0.15, 0.06),
            (0.19, 0.00),
            (0.23, 0.06),
            (0.27, 0.00),
        ],
        [
            (0.05, 0.12),
            (0.11, 0.20),
            (0.19, 0.18),
            (0.27, 0.20),
            (0.33, 0.12),
        ],
    )
    hm.to_dxf()
    assert hm.to_pat_str() == expected


@pytest.mark.parametrize(
    'angle_step',
    [0.5, 1, 5, 10, 30]
)
def test_multiple_angles(angle_step):
    angles = np.arange(0, 360 + angle_step, angle_step)
    angle_rad = np.deg2rad(angles)
    p1 = list(zip(0.1 * np.cos(angle_rad), 0.1 * np.sin(angle_rad)))
    p0 = [(0, 0)] * len(p1)
    hm = HatchMaker(pat_title=f'test_multiple_angles_{angle_step=}').set_from_points(
        p0, p1,
        round_decimals=4,
    )
    hm.to_dxf()
