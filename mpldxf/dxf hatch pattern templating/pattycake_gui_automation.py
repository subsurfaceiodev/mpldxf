import pandas as pd
import pyautogui as pg
import pygetwindow as gw
from mpldxf.hatchmaker import HatchMaker
from tkinter import Tk
import numpy as np
from fractions import Fraction

gw.getWindowsWithTitle('- Pattycake')[0].maximize()


def get_df(canvas_width, canvas_dimension_is):
    # click on advanced settings
    pg.click(1043, 215)
    if canvas_dimension_is == 'width':
        # click on canvas width field
        pg.click(804, 349)
    elif canvas_dimension_is == 'height':
        # click on canvas height field
        pg.click(804, 383)
    else:
        raise Exception(f'{canvas_dimension_is=} not valid')
    # select all
    pg.hotkey('ctrl', 'a')
    pg.typewrite(str(canvas_width))
    # click on save settings
    pg.click(1223, 731)
    # click on pat preview text area
    pg.click(1500, 350)
    # select all
    pg.hotkey('ctrl', 'a')
    # copy to clipboard
    pg.hotkey('ctrl', 'c')
    pat_str = Tk().clipboard_get()
    df = HatchMaker.read_pat_str_as_df(pat_str)
    return df


# pattycake won't accept canvas width or height values less than 0.125!
canvas_dimensions = np.arange(0.13, 4 + 0.01, 0.01)
canvas_dimension_is = 'height'
# canvas_dimensions = [0.125, 0.14, 0.2, 0.3]
dfs = {}
for canvas_dimension in canvas_dimensions:
    canvas_dimension = round(canvas_dimension, 3)

    try:
        df = get_df(canvas_dimension, canvas_dimension_is=canvas_dimension_is)
    except pd.errors.EmptyDataError as e:
        df = pd.DataFrame([{'angle': np.nan}])

    dfs[canvas_dimension] = df
dfs = pd.concat(dfs, names=[f'canvas_{canvas_dimension_is}']).droplevel(1)
dfs['d'] = dfs['dash'] + dfs['space'].abs()
angle = dfs['angle'].iloc[0]
angle_rad = np.deg2rad(angle)
sin_angle = np.sin(angle_rad)
tan_angle = np.tan(angle_rad)
angle_fraction = Fraction(tan_angle).limit_denominator(max_denominator=100)
dfs['d_y'] = sin_angle * dfs['d']
dfs['d_x'] = dfs['d_y'] / tan_angle
dfs['multiplier'] = dfs['d_x'] / angle_fraction.denominator
dfs.to_excel(f'canvas_{canvas_dimension_is}s_pats.xlsx')
print(dfs)
