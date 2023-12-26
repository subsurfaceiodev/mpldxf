import pandas as pd
import pyautogui as pg
import pygetwindow as gw
from mpldxf.hatchmaker import HatchMaker
from tkinter import Tk
import numpy as np
from fractions import Fraction

gw.getWindowsWithTitle('- Pattycake')[0].maximize()


def get_df(canvas_width):
    # click on advanced settings
    pg.click(1043, 215)
    # click on canvas width field
    pg.click(804, 349)
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


canvas_widths = np.arange(0.1, 4 + 0.01, 0.01)
# canvas_widths = [0.1, 0.14, 0.2, 0.3]
dfs = {}
for canvas_width in canvas_widths:
    canvas_width = round(canvas_width, 3)

    try:
        df = get_df(canvas_width)
    except pd.errors.EmptyDataError as e:
        df = pd.DataFrame([{'angle': np.nan}])

    dfs[canvas_width] = df
dfs = pd.concat(dfs, names=['canvas_width']).droplevel(1)
print(dfs)
dfs['d'] = dfs['dash'] + dfs['space'].abs()
angle = dfs['angle'].iloc[0]
angle_rad = np.deg2rad(angle)
sin_angle = np.sin(angle_rad)
tan_angle = np.tan(angle_rad)
angle_fraction = Fraction(tan_angle).limit_denominator(max_denominator=100)
dfs['d_y'] = sin_angle * dfs['d']
dfs['d_x'] = dfs['d_y'] / tan_angle
dfs['multiplier'] = dfs['d_x'] / angle_fraction.denominator
dfs.to_excel('canvas_widths_pats.xlsx')
print(dfs)
