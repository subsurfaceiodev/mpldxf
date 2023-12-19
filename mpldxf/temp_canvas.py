from mpldxf.hatchmaker import HatchMaker

hm = HatchMaker(
    pat_title='test_pattycake'
).set_from_points(
    [
        (0.125, 0.05),
        (0.125, 0.125),
        # (0.0366, 0.2134),
        # (0.375, 0.3179),
        # (0.375, 0.375),
        # (0.2866, 0.4634),
        (0, 0),
        (0.25, 0),
        (0, 0),
    ],
    [
        (0.125, 0.125),
        (0.2134, 0.2134),
        # (0.125, 0.125),
        # (0.375, 0.375),
        # (0.4634, 0.4634),
        # (0.375, 0.375),
        (0.25, 0),
        (0.25, 0.25),
        (1 / 2, 0.57735 / 2),
    ],
    canvas_height=1,
    canvas_width=0.5,
    round_decimals=4,
)
print(hm.to_pat_str())
hm.to_dxf()
