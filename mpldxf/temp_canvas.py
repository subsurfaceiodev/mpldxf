import pandas as pd

from mpldxf.hatchmaker import HatchMaker, clean_pat_title

bp = 'dxf hatch pattern templating'


def show_canvas_effect():
    df_map = {}
    canvas_list = [
        '0.50X0.50',
        '0.75X0.75',
        '1.00X0.50',
        '0.50X1.00',
        '1.00X1.00',
        '1.00X1.50',
        '1.25X1.25',
        '1.50X1.50',
    ]
    for canvas in canvas_list:
        df = HatchMaker.read_pat_as_df(f'{bp}/5 x .5 Star Burst {canvas}.pat')
        print(canvas)
        print(HatchMaker.df_to_points(df))
        df_map[canvas] = df
    df_map = pd.concat(df_map)
    print(df_map.to_string())
    df_map_div = {}
    for canvas in canvas_list:
        df_map_div[canvas] = df_map.loc[canvas] / df_map.loc['1.00X1.00']
    df_map_div = pd.concat(df_map_div)[['shift', 'offset', 'space']]
    print(df_map_div.to_string())


# show_canvas_effect()

for canvas in [
    # (0.5, 1),
    (1, 1),
    (2, 1),
    (1, 2),
    (3, 1.5),
]:
    canvas_width, canvas_height = canvas
    hm = HatchMaker(
        pat_title=f'test_pattycake_{canvas_width}_{canvas_height}'
    ).set_from_points(
        [
            (0.25, 0.4688),
            (0.4688, 0.25),
            (0.125, 0.375),
            (0.375, 0.375),
            (0.0938, 0.1875),
            (0.0938, 0.3125),
            (0.3125, 0.4063),
            (0.1875, 0.4063),
        ],
        [
            (0.25, 0.0313),
            (0.0313, 0.25),
            (0.375, 0.125),
            (0.125, 0.125),
            (0.4063, 0.3125),
            (0.4063, 0.1875),
            (0.1875, 0.0938),
            (0.3125, 0.0938),
        ],
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        round_decimals=4,
    )
    print(hm.to_pat_str())
    pat_fname = clean_pat_title(f'5x5StarBurst{canvas_width}_{canvas_height}')
    hm.to_dxf()

hm = HatchMaker().set_from_points(
    [
        (0, 0),
        (0, 0),
        (0, 0),
        (0, 0),
    ],
    [
        (0.5, 0.2),
        (2, 0.3),
        (0.113, 0.993),
        (0.985, 0.174),
    ],
    canvas_width=1.13,
    canvas_height=0.51,
    round_decimals=4
)
print(hm)
hm.to_dxf()
