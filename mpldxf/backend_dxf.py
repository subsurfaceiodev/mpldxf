"""
A backend to export DXF using a custom DXF renderer.

This allows saving of DXF figures.

Use as a matplotlib external backend:

  import matplotlib
  matplotlib.use('module://mpldxf.backend_dxf')

or register:

  matplotlib.backend_bases.register_backend('dxf', FigureCanvasDXF)

Based on matplotlib.backends.backend_template.py.

Copyright (C) 2014 David M Kent

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import math
import os
import sys
from fractions import Fraction
from itertools import pairwise

import ezdxf
import ezdxf.math.clipping
import matplotlib as mpl
import numpy as np
from ezdxf.enums import TextEntityAlignment
from matplotlib.backend_bases import (RendererBase, FigureCanvasBase,
                                      GraphicsContextBase, FigureManagerBase)
from matplotlib.backend_bases import _Backend
from matplotlib.transforms import Affine2D
from scipy.special import cosdg, tandg
from shapely.geometry import LineString, Polygon

from mpldxf.HatchMaker import hatchmaker, hatchmaker_single, rotate, get_angle, data_to_string
from mpldxf.HatchMakerSSIO import hatchmaker as hatchmakerSSIO


# When packaged with py2exe ezdxf has issues finding its templates
# We tell it where to find them using this.
# Note we also need to make sure they get packaged by adding them to the
# configuration in setup.py
if hasattr(sys, 'frozen'):
    ezdxf.options.template_dir = os.path.dirname(sys.executable)


def get_color_attribs(rgb_val):
    """Convert an RGB[A] colour to DXF colour index.

       ``rgb_val`` should be a tuple of values in range 0.0 - 1.0. Any
       alpha value is ignored.
    """
    attribs = {}
    if rgb_val is None:
        attribs['color'] = 7
    # change black to white
    elif np.allclose(np.array(rgb_val[:3]), np.zeros(3)):
        attribs['color'] = 7
    else:
        attribs['true_color'] = ezdxf.rgb2int(
            [255.0 * val for val in rgb_val[:3]]
        )
    return attribs


# print(get_angle_offsets(np.deg2rad(72.121), round_precision=3))


# get_angle_offsets_vec = np.vectorize(get_angle_offsets, otypes=[float, float, float], excluded=['round_precision'])
#
# import pandas as pd
#
# df = pd.read_excel('dxf hatch pattern templating/analyze mod.xlsx', skiprows=1, index_col=[0, 1])
# # df = df.loc[['Pattycake.com']]
# for i, r in df.iterrows():
#     angle, d, dy = r['angle'], r['dash solid+gap'], r['dy']
#     x_, y_, d_, dy_ = get_angle_offsets(angle, round_precision=3)
#     print(angle, round(d / d_, 2), round(dy / dy_, 2))
#
# angles = np.arange(0, 360.5, 0.5)
# dx, dy, d = get_angle_offsets_vec(angles, round_precision=3)
# vs = dy
# import matplotlib.pyplot as plt
#
# plt.plot(angles, vs)
# plt.show()

# print(get_hatch_pattern_args_inprogress((0, 0), (0, -1)))

# print(get_hatch_pattern_args_inprogress((0, 0), (0, -1), dxf_mode=True))
# args = get_hatch_pattern_args_inprogress([1, 1], [1 + 0.0866, 1 + 0.05], sidelength=2)
# args_PAT_format = ','.join(
#     [str(x) if not isinstance(x, (list, tuple)) else ','.join([str(y) for y in x]) for x in args.values()])
# print(args_PAT_format)


class RendererDXF(RendererBase):
    """
    The renderer handles drawing/rendering operations.

    Renders the drawing using the ``ezdxf`` package.
    """

    def __init__(self, width, height, dpi, dxfversion):
        RendererBase.__init__(self)
        self.height = height
        self.width = width
        self.dpi = dpi
        self.dxfversion = dxfversion
        self._init_drawing()
        self._groupd = []

    def _init_drawing(self):
        """Create a drawing, set some global information and add
           the layers we need.
        """
        drawing = ezdxf.new(dxfversion=self.dxfversion, setup=True)
        drawing.styles.add('Arial', font='Arial.ttf')
        modelspace = drawing.modelspace()
        drawing.header['$EXTMIN'] = (0, 0, 0)
        drawing.header['$EXTMAX'] = (self.width, self.height, 0)
        drawing.header["$LWDISPLAY"] = 1
        layout = drawing.layout('Layout1')
        paper_size_mm = (self.width / 100 * 25.4, self.height / 100 * 25.4)
        layout.page_setup(
            size=paper_size_mm,
            margins=(0, 0, 0, 0),
        )
        layout.add_viewport(
            center=(paper_size_mm[0] * 0.5, paper_size_mm[1] * 0.5),
            size=paper_size_mm,
            view_center_point=(self.width * 0.5, self.height * 0.5),
            view_height=self.height,
        )
        self.drawing = drawing
        self.modelspace = modelspace

    def clear(self):
        """Reset the renderer."""
        super(RendererDXF, self).clear()
        self._init_drawing()

    def _get_polyline_attribs(self, gc):
        attribs = {**get_color_attribs(gc.get_rgb())}
        offset, seq = gc.get_dashes()
        if seq is not None:
            # print(offset, seq)
            # attribs['linetype'] = 'DASHED'
            name = str(np.array(seq).round(2))
            if name not in self.drawing.linetypes:
                pattern = [sum(seq), *[-s if si % 2 else s for si, s in enumerate(seq)]]
                # print(pattern)
                # pattern = [0.2, 0.0, -0.2]
                self.drawing.linetypes.add(
                    name=name,
                    pattern=pattern,
                    description=name,
                )
            attribs['linetype'] = name
        attribs['lineweight'] = self.points_to_pixels(gc.get_linewidth()) * 10 * 2
        return attribs

    def set_entity_attribs(self, gc, entity):
        alpha = gc.get_alpha() if gc.get_forced_alpha() else gc.get_rgb()[3]
        if alpha != 1:  # is alpha != 0 correct for all cases?
            entity.transparency = 1 - alpha

    def _clip_mpl(self, gc, vertices, obj):
        # clip the polygon if clip rectangle present
        bbox = gc.get_clip_rectangle()
        if bbox is not None:
            cliprect = [[bbox.x0, bbox.y0],
                        [bbox.x1, bbox.y0],
                        [bbox.x1, bbox.y1],
                        [bbox.x0, bbox.y1]]

            if obj in ['patch', 'line2d']:
                vertices = ezdxf.math.clipping.clip_polygon_2d(cliprect, vertices)
            # elif obj == 'line2d':
            #     cliprect = Polygon(cliprect)
            #     line = LineString(vertices)
            #     vertices = line.intersection(cliprect).coords

        return vertices

    def _draw_mpl_lwpoly(self, gc, path, transform, obj):
        # TODO rework for BEZIER curves
        # if obj in ['patch', 'QuadMesh', 'Poly3DCollection']:
        #     close = True
        # elif obj in ['line2d', 'LineCollection', 'Line3DCollection', 'PathCollection']:
        #     close = False
        # else:
        #     raise NotImplementedError

        dxfattribs = self._get_polyline_attribs(gc)
        vertices = path.transformed(transform).vertices
        if obj in ['patch'] or vertices.size != 0 and (vertices[0] == vertices[-1]).all():
            close = True
        else:
            close = False

        # clip the polygon if clip rectangle present
        vertices = self._clip_mpl(gc, vertices, obj=obj)

        entity = self.modelspace.add_lwpolyline(points=vertices,
                                                close=close,
                                                dxfattribs=dxfattribs)
        self.set_entity_attribs(gc, entity)
        return entity

    def _draw_mpl_patch(self, gc, path, transform, rgbFace=None, obj=None):
        '''Draw a matplotlib patch object
        '''

        poly = self._draw_mpl_lwpoly(gc, path, transform, obj=obj)

        # check to see if the patch is filled
        if rgbFace is not None:
            hatch = self.modelspace.add_hatch(dxfattribs=get_color_attribs(rgbFace))  # dxfattribs=get_color_attribs(rgbFace)
            self.set_entity_attribs(gc, hatch)
            def method1():
                hpath = gc.get_hatch_path()
                sidelen = 1
                if hpath is not None:
                    patterns = []
                    hpath_unit = mpl.hatch.get_path(gc._hatch)  # , density=6 might need some clipping

                    polys = hpath_unit.to_polygons(closed_only=False)
                    # print(len(polys))
                    # print(len(hpath_unit.vertices))
                    import matplotlib.pyplot as plt
                    fig, ax = plt.subplots()
                    for poly_ in polys:
                        # poly_ *= sidelen
                        # if (poly_ > sidelen).any() or (poly_ < 0).any():
                        #     continue
                        for p0, p1 in pairwise(poly_):
                            pattern = hatchmakerSSIO(p0, p1, dxf_mode=True, return_as_string=False)
                            patterns.append(pattern)
                            # else:
                            #     # pass
                            #     print(p0, p1)
                            #     # sdfgdfgdfg
                            # p0 = np.round(p0, 3)
                            # p1 = np.round(p1, 3)
                            # pattern_args = get_hatch_pattern_args_inprogress(p0, p1, sidelength=sidelen, dxf_mode=True)
                            #
                            # pattern_args = hatchmaker_single(p0, p1, dxf_mode=True, return_as_data=True)
                            # # print(get_hatch_pattern_args_inprogress(p0, p1, dxf_mode=False, return_as_string=True))
                            # strcat = hatchmaker_single(p0, p1)
                            # if strcat is not None:
                            #     print(strcat)
                            # else:
                            #     print('AAAAAAAAAAAAAAAAAAAA')
                            # # print(','.join(
                            # #     [','.join([str(x_) for x_ in x]) if isinstance(x, (np.ndarray, list, tuple)) else str(x) for
                            # #      x in pattern_args.values()]))
                            # # print(pattern_args)
                            #
                            # pattern.append([*pattern_args.values()])
                        x_ = poly_[:, 0]
                        y_ = poly_[:, 1]
                        ax.plot(x_, y_)
                    # print(hatchmaker(p0, p1, dxf_mode=False, return_as_data=False))
                    # pattern.extend(pattern_)

                    fig.savefig('temp/temp.pdf')
                    patterns = [list(d.values()) for d in patterns]
                    hatch.set_pattern_fill(
                        name=f'mpl_{gc._hatch}',
                        style=1,
                        pattern_type=1,
                        scale=100,
                        definition=patterns,
                    )

            def method2():
                self._draw_mpl_hatch(gc, path, transform, pline=poly)

            method1()
            hpath = hatch.paths.add_polyline_path(
                # get path vertices from associated LWPOLYLINE entity
                poly.get_points(format="xyb"),
                # get closed state also from associated LWPOLYLINE entity
                is_closed=poly.closed)

            # Set association between boundary path and LWPOLYLINE
            hatch.associate(hpath, [poly])

    def _draw_mpl_hatch(self, gc, path, transform, pline):
        '''Draw MPL hatch
        '''

        hatch = gc.get_hatch()
        if hatch is not None:
            # find extents and center of the original unclipped parent path
            ext = path.get_extents(transform=transform)
            dx = ext.x1 - ext.x0
            cx = 0.5 * (ext.x1 + ext.x0)
            dy = ext.y1 - ext.y0
            cy = 0.5 * (ext.y1 + ext.y0)

            # matplotlib uses a 1-inch square hatch, so find out how many rows
            # and columns will be needed to fill the parent path
            rows, cols = math.ceil(dy / self.dpi) - 1, math.ceil(dx / self.dpi) - 1

            # get color of the hatch
            rgb = gc.get_hatch_color()
            dxfattribs = get_color_attribs(rgb)

            # get hatch paths
            hpath = gc.get_hatch_path()

            # this is a transform that produces a properly scaled hatch in the center
            # of the parent hatch
            _transform = Affine2D().translate(-0.5, -0.5).scale(self.dpi).translate(cx, cy)
            hpatht = hpath.transformed(_transform)

            # print("\tHatch Path:", hpatht)
            # now place the hatch to cover the parent path
            for irow in range(-rows, rows + 1):
                for icol in range(-cols, cols + 1):
                    # transformation from the center of the parent path
                    _trans = Affine2D().translate(icol * self.dpi, irow * self.dpi)
                    # transformed hatch
                    _hpath = hpatht.transformed(_trans)

                    # turn into list of vertices to make up polygon
                    _path = _hpath.to_polygons(closed_only=False)

                    for vertices in _path:
                        # clip each set to the parent path
                        if len(vertices) == 2:
                            clippoly = Polygon(pline.vertices())
                            line = LineString(vertices)
                            try:
                                clipped = line.intersection(clippoly).coords
                            except NotImplementedError:
                                continue  # PENDING TO FIX WHEN SAVING LOGPLOT
                        else:
                            try:
                                clipped = ezdxf.math.clipping.clip_polygon_2d(pline.vertices(), vertices)
                            except ValueError:
                                continue  # PENDING TO FIX WHEN SAVING LOGPLOT

                        # if there is something to plot
                        if len(clipped) > 0:
                            if len(vertices) == 2:
                                entity = self.modelspace.add_lwpolyline(points=clipped,
                                                                        dxfattribs=dxfattribs)

                            else:
                                # A non-filled polygon or a line - use LWPOLYLINE entity
                                entity = self.modelspace.add_hatch(dxfattribs=dxfattribs)
                                line = entity.paths.add_polyline_path(clipped)
                            self.set_entity_attribs(gc, entity)

    def draw_path(self, gc, path, transform, rgbFace=None):
        # print('\nEntered ###DRAW_PATH###')
        # print('\t', self._groupd)
        # print('\t', gc.__dict__, rgbFace)
        # print('\t', gc.get_sketch_params())
        # print('\tMain Path', path.__dict__)
        # hatch = gc.get_hatch()
        # if hatch is not None:
        #     print('\tHatch Path', gc.get_hatch_path().__dict__)
        self._draw_mpl_patch(gc, path, transform, rgbFace, obj=self._groupd[-1])

    # # Note if this is used then tick marks and lines with markers go through this function
    # def draw_markers(self, gc, marker_path, marker_trans, path, trans, rgbFace=None):
    #     # print('\nEntered ###DRAW_MARKERS###')
    #     # print('\t', self._groupd)
    #     # print('\t', gc.__dict__)
    #     # print('\tMarker Path:', type(marker_path), marker_path.transformed(marker_trans).__dict__)
    #     # print('\tPath:', type(path), path.transformed(trans).__dict__)
    #     if (self._groupd[-1] == 'line2d') & ('tick' in self._groupd[-2]):
    #         newpath = path.transformed(trans)
    #         dx, dy = newpath.vertices[0]
    #         _trans = marker_trans + Affine2D().translate(dx, dy)
    #         line = self._draw_mpl_line2d(gc, marker_path, _trans)
    #     # print('\tLeft ###DRAW_MARKERS###')

    def draw_image(self, gc, x, y, im, transform=None):
        pass

    def draw_text(self, gc, x, y, s, prop, angle, ismath=False, mtext=None):

        bbox = gc.get_clip_rectangle()

        if bbox is not None:
            # ignore text outside bbox
            if not bbox.x0 <= x <= bbox.x1 or not bbox.y0 <= y <= bbox.y1:
                return

        if ismath:
            width, height, descent, glyphs, rects = \
                self._text2path.mathtext_parser.parse(s, 72, prop)
            s_parsed = ''
            fontsize_prev = None
            for font, fontsize, num, ox, oy in glyphs:
                s_parsed_current = chr(num)
                if fontsize_prev is not None and fontsize < fontsize_prev:
                    DIGITS = dict(zip(u"0123456789", u"⁰¹²³⁴⁵⁶⁷⁸⁹"))
                    s_parsed_current = DIGITS.get(s_parsed_current, s_parsed_current)
                s_parsed += s_parsed_current
                fontsize_prev = fontsize
            s = s_parsed

        # print('\nEntered ###DRAW_TEXT###')
        # print('\t', self._groupd)
        # print('\t', gc.__dict__)

        # fontsize = self.points_to_pixels(prop.get_size_in_points()) original
        fontsize = prop.get_size_in_points()

        # s = s.replace(u"\u2212", "-")
        s.encode('ascii', 'ignore').decode()
        text = self.modelspace.add_text(s, height=fontsize, rotation=angle, dxfattribs={
            **get_color_attribs(gc.get_rgb()),
            'style': 'Arial',
        })
        self.set_entity_attribs(gc, text)

        if mtext and (angle != 90 or mtext.get_rotation_mode() == "anchor"):
            halign = self._map_align(mtext.get_ha(), vert=False)
            valign = self._map_align(mtext.get_va(), vert=True)
            align = valign
            if align:
                align += '_'
            align += halign
            # need to get original points for text anchoring
            pos = mtext.get_unitless_position()
            x, y = mtext.get_transform().transform(pos)
        else:
            align = 'LEFT'

        align = getattr(TextEntityAlignment, align)

        p1 = x, y
        text.set_placement(p1, align=align)
        # print('Left ###TEXT###')

    def _map_align(self, align, vert=False):
        """Translate a matplotlib text alignment to the ezdxf alignment."""
        if align in ['right', 'center', 'left', 'top',
                     'bottom', 'middle']:
            align = align.upper()
        elif align == 'baseline':
            align = ''
        elif align == 'center_baseline':
            align = 'MIDDLE'
        else:
            # print(align)
            raise NotImplementedError
        if vert and align == 'CENTER':
            align = 'MIDDLE'
        return align

    def open_group(self, s, gid=None):
        # docstring inherited
        self._groupd.append(s)

    def close_group(self, s):
        self._groupd.pop(-1)

    def flipy(self):
        return False

    def get_canvas_width_height(self):
        return self.width, self.height

    def new_gc(self):
        return GraphicsContextBase()

    def points_to_pixels(self, points):
        return points / 72.0 * self.dpi


class FigureCanvasDXF(FigureCanvasBase):
    """
    A canvas to use the renderer. This only implements enough of the
    API to allow the export of DXF to file.
    """

    #: The DXF version to use. This can be set to another version
    #: supported by ezdxf if desired.
    DXFVERSION = 'AC1032'

    def get_dxf_renderer(self, cleared=False):
        """Get a renderer to use. Will create a new one if we don't
           alreadty have one or if the figure dimensions or resolution have
           changed.
        """
        l, b, w, h = self.figure.bbox.bounds
        key = w, h, self.figure.dpi
        try:
            self._lastKey, self.dxf_renderer
        except AttributeError:
            need_new_renderer = True
        else:
            need_new_renderer = (self._lastKey != key)

        if need_new_renderer:
            self.dxf_renderer = RendererDXF(w, h, self.figure.dpi,
                                            self.DXFVERSION)
            self._lastKey = key
        elif cleared:
            self.dxf_renderer.clear()
        return self.dxf_renderer

    def draw(self):
        """
        Draw the figure using the renderer
        """
        renderer = self.get_dxf_renderer()
        self.figure.draw(renderer)
        return renderer.drawing

    # Add DXF to the class-scope filetypes dictionary
    filetypes = {**FigureCanvasBase.filetypes, 'dxf': 'Drawing Exchange Format'}

    def print_dxf(self, filename, *args, **kwargs):
        """
        Write out a DXF file.
        """
        drawing = self.draw()
        drawing.saveas(filename)

    def get_default_filetype(self):
        return 'dxf'


@_Backend.export
class _BackendDXF(_Backend):
    FigureCanvas = FigureCanvasDXF
    FigureManagerDXF = FigureManagerBase
