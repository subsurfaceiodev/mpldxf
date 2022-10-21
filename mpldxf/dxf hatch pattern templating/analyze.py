from glob import glob

import pandas as pd
from scipy.special import cosdg, sindg
df_d = {}
for fname in glob('*.pat'):
    df_d[fname] = pd.read_csv(fname, skiprows=1, header=None)
df = pd.concat(df_d, names=['ID', 'idx'])
df.columns = ['angle', 'x', 'y', 'dx', 'dy', 'dash_solid', 'dash_gap']
df['cos angle'] = cosdg(df['angle'])
df['sin angle'] = sindg(df['angle'])
print(df.to_string())
df.to_excel('analyze.xlsx')