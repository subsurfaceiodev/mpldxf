import pathlib

import pandas as pd

filepath = pathlib.Path(__file__).resolve().parent

HATCH_SAMPLES = pd.read_pickle(f'{filepath}/HATCH_SAMPLES.pickle')
