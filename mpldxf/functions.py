import numpy as np
from shapely.geometry import LineString, Polygon, MultiLineString
from shapely.ops import linemerge


def clip_geometry(vertices, clippoly):
    # clip the polygon if clip rectangle present
    if not isinstance(vertices, LineString) and len(vertices) < 2:  # ignore single points
        return None

    shape = LineString(vertices)

    if not clippoly.contains(shape) and not clippoly.intersects(shape):
        return None

    if not shape.is_simple:
        # when shape crosses itself shapely contains, etc. does not work
        # correctly, so we split the shape, clip individual segments and
        # join them back as a single array
        vertices_all = []
        for pt1, pt2 in zip(shape.coords, shape.coords[1:]):
            vertices_ = np.array([pt1, pt2])
            vertices_ = clip_geometry(vertices_, clippoly)
            if vertices_ is not None:
                vertices_all.append(vertices_)
        vertices_all = np.concatenate(vertices_all, axis=0)
        return vertices_all
    shape = shape.intersection(clippoly)
    if shape.geom_type == 'MultiLineString':
        shape = linemerge(shape)
    if shape.geom_type == 'MultiLineString':
        vertices_all = []
        for shape_ in shape.geoms:
            vertices_ = clip_geometry(shape_, clippoly)
            if vertices_ is not None:
                vertices_all.append(vertices_)
        vertices_all = np.concatenate(vertices_all, axis=0)
        return vertices_all
    if shape.geom_type == 'MultiPoint':
        # very rare cases like 's650'
        shape = LineString([x for x in shape.geoms])
        return clip_geometry(shape, clippoly)
    if shape.geom_type != 'LineString':
        # very rare cases like 's650'
        return None
    vertices = np.array(list(zip(*shape.coords.xy)))
    if vertices.size == 0:
        return None
    return vertices


def fill_polygon_with_lines(polygon, delta=0.025):
    # polygon = Polygon([(0, 0), (1, 0.5), (1, 0.7), (0.5, 1)])
    minx, miny, maxx, maxy = polygon.bounds
    lines = []

    for x in np.arange(minx, maxx, delta):
        line = LineString([(x, miny), (x, maxy)]).intersection(polygon)
        lines.append(line)
    for y in np.arange(miny, maxy, delta):
        line = LineString([(minx, y), (maxx, y)]).intersection(polygon)
        lines.append(line)
    # if lines.geom_type == 'LineString':
    #     return []
    lines = [np.vstack(line.coords.xy).T for line in lines]
    return lines
