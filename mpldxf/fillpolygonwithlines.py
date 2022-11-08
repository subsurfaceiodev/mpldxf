import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import LineString, Polygon
DELTA = 0.025
polygon = Polygon([(0, 0), (1, 0.5), (1, 0.7), (0.5, 1)])
minx, miny, maxx, maxy = polygon.bounds
for x in np.arange(minx, maxx, DELTA):
    line = LineString([(x, miny), (x, maxy)])
    line = line.intersection(polygon)
    plt.plot(*line.xy, c='k')
for y in np.arange(miny, maxy, DELTA):
    line = LineString([(minx, y), (maxx, y)])
    line = line.intersection(polygon)
    plt.plot(*line.xy, c='k')

plt.plot(*polygon.exterior.xy)
plt.show()