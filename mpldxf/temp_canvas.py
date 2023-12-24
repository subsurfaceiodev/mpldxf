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
    (0.5, 1),
    (1, 1),
    (2, 1),
    # (1, 2),
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
            (0.1875, 0.4063)
        ],
        [
            (0.25, 0.0313),
            (0.0313, 0.25),
            (0.375, 0.125),
            (0.125, 0.125),
            (0.4063, 0.3125),
            (0.4063, 0.1875),
            (0.1875, 0.0938),
            (0.3125, 0.0938)
        ],
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        round_decimals=4,
    )
    print(hm.to_pat_str())
    # expected_map = {
    #     '0.50X0.50': '21.80140949,0.0938,0.1875,1.57841038,-0.09284767,0.3365728,-2.3560096',
    #     '0.50X1.00': '21.801409486,0.0938,0.1875,0.464238345,-0.185695338,0.3365728,-2.356009603',
    #     '0.75X1.00': '21.80140949,0.0938,0.1875,5.61728398,-0.09284767,0.3365728,-7.74117441',
    #     '1.50X1.00': '21.80140949,0.0938,0.1875,3.15682075,-0.18569534,0.3365728,-7.74117441',
    # }
    # expected = expected_map['1.50X1.00']
    pat_fname = clean_pat_title(f'5x5StarBurst{canvas_width}_{canvas_height}')
    df = HatchMaker.read_pat_as_df(f'{bp}/{pat_fname}.pat')
    print(df)
    hm.to_dxf()
