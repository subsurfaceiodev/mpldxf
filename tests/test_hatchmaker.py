import numpy as np
from mpldxf.HatchMaker import HatchMaker


def test_single():
    hl = HatchMaker(
        pat_title='test_single'
    ).set_from_points(
        [(0.72, 1), (0.63, 0.9), (0.4, 0.88), (0, 0), (0, 0)],
        [(0.63, 0.9), (0.4, 0.88), (0.29, 1), (0.2575, 0.5), (1, 0)],
    )
    hl.to_dxf()
    print(hl.to_pat_str())


def test_multiple_angles(angle_step=0.5):
    angles = np.arange(0, 360 + angle_step, angle_step)
    angle_rad = np.deg2rad(angles)
    p1 = list(zip(0.1 * np.cos(angle_rad), 0.1 * np.sin(angle_rad)))
    p0 = [(0, 0)] * len(p1)
    HatchMaker(pat_title='test_multiple_angles').set_from_points(
        p0, p1,
        round_decimals=4,
    ).to_dxf()
