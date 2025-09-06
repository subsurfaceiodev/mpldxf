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

import logging
import math
import os
import sys
import warnings

import ezdxf
import ezdxf.math.clipping
import numpy as np
from ezdxf.enums import TextEntityAlignment
from fontTools.ttLib import TTFont
from matplotlib import font_manager
from matplotlib.backend_bases import (RendererBase, FigureCanvasBase,
                                      GraphicsContextBase, FigureManagerBase)
from matplotlib.backend_bases import _Backend
from matplotlib.transforms import Affine2D
from shapely.errors import GEOSException
from shapely.geometry import box, LineString, Polygon
from shapely.ops import linemerge
from mpldxf.functions import clip_geometry

_log = logging.getLogger(__name__)

# fonts in site-packages\matplotlib\mpl-data\fonts\ttf should be installed on local
# machine first for CAD software to recognize them
TTF_FILES = {}
for ttf_path in font_manager.findSystemFonts(fontpaths=None, fontext='ttf'):
    ttf_file = os.path.basename(ttf_path)
    if not ('.ttf' in ttf_file or '.TTF' in ttf_file):
        continue
    with TTFont(ttf_path) as ttfont:
        names = ttfont['name'].names
        family = str(names[1])
        style = str(names[2])
        TTF_FILES[ttf_file] = dict(family=family, bold='Bold' in style, italic='Italic' in style)

# TODO: Multiline text like in logplot not breaking lines correctly.:
#       commenting points_to_pixels functions makes identical text wrapping but changes font position
#       shapely filterwarnings should not be needed now?.
#       use _log for better future code debugging
#       linestyles test not displaying some lines correctly (DONE)
#       acad.ctb (for correct square linetypes) and plot transparency as defaults in layout

# When packaged with py2exe ezdxf has issues finding its templates
# We tell it where to find them using this.
# note we also need to make sure they get packaged by adding them to the
# configuration in setup.py
if hasattr(sys, 'frozen'):
    ezdxf.options.template_dir = os.path.dirname(sys.executable)

warnings.filterwarnings('ignore', 'invalid value encountered in contains')
warnings.filterwarnings('ignore', 'invalid value encountered in intersects')
warnings.filterwarnings('ignore', 'invalid value encountered in intersection')


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
            255 * np.array(rgb_val[:3])
        )
    return attribs


HATCH_SCALE_FACTOR = 0.5  # * 0.5 to match pdf modified hatch density
HATCH_LINES_DRAW_AS_PAT = False
# https://stackoverflow.com/questions/47633546/relationship-between-dpi-and-figure-size
# 1 / 72 to convert points to inches
# 25.4 to convert inches to mm
# 100 to get value in mm times 100 as dxf requirement
# 1 / 72 * 100 is already covered by points_to_pixels functions
# so only 25.4 is left
# note that ezdxf automatically chooses nearest line width from limited set
# of dxf values available, so in some cases line widths won't be exact
LINEWIDTH_FACTOR = 25.4


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
        for ttf_file, extended_data in TTF_FILES.items():
            text_style = drawing.styles.add(ttf_file, font=ttf_file)
            text_style.set_extended_font_data(**extended_data)

        modelspace = drawing.modelspace()
        drawing.header['$EXTMIN'] = (0, 0, 0)
        drawing.header['$EXTMAX'] = (self.width, self.height, 0)
        drawing.header["$LWDISPLAY"] = 1
        drawing.header['$PSLTSCALE'] = 0
        drawing.header['$PLINEGEN'] = 1
        HIDDEN_LAYER = drawing.layers.add('HIDDEN')
        HIDDEN_LAYER.off()
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
            dxfattribs=dict(status=-1),  # set to not active
        )
        self.drawing = drawing
        self.modelspace = modelspace

    def clear(self):
        """Reset the renderer."""
        super(RendererDXF, self).clear()
        self._init_drawing()

    def check_gc(self, gc):
        gc._lineweight = self.points_to_pixels(gc.get_linewidth()) * LINEWIDTH_FACTOR
        gc._hatch_lineweight = self.points_to_pixels(gc.get_hatch_linewidth()) * LINEWIDTH_FACTOR

        gc._linetype = None
        offset, seq = gc.get_dashes()  # offset not considered
        if seq is not None:
            FACTOR = self.points_to_pixels(1)
            pattern_pattern = np.array([FACTOR * (-s if si % 2 else s) for si, s in enumerate(seq)])
            name = str(pattern_pattern.round(2))
            if name not in self.drawing.linetypes:
                pattern = [np.sum(pattern_pattern, where=pattern_pattern > 0), *pattern_pattern]
                self.drawing.linetypes.add(
                    name=name,
                    pattern=pattern,
                    description=name,
                )
            gc._linetype = name

        gc._transparency = None
        if gc.get_forced_alpha():
            alpha = gc.get_alpha()
            if alpha != 1:
                gc._transparency = 1 - alpha
        else:
            alpha = gc.get_rgb()[3]
            if alpha != 0 and alpha != 1:
                gc._transparency = 1 - alpha

    def _get_polyline_attribs(self, gc):
        attribs = {**get_color_attribs(gc.get_rgb())}
        if gc._linetype is not None:
            attribs['linetype'] = gc._linetype
        attribs['lineweight'] = gc._lineweight
        if attribs['lineweight'] == 0 or gc.get_rgb() is None:
            attribs['layer'] = 'HIDDEN'
        return attribs

    def set_entity_attribs(self, gc, entity):
        if gc._transparency is not None:
            entity.transparency = gc._transparency

    def _clip_mpl(self, vertices, clippoly):
        return clip_geometry(vertices, clippoly)

    def _draw_mpl_patch(self, gc, path, transform, rgbFace=None, obj=None):
        '''Draw a matplotlib patch object
        '''
        # Using clip = bbox in path.cleaned and width / height attributes in path.to_polygons
        # would be great, but it does not work correctly for some cases (e.g. it splits polygons
        # when they are clipped) so hatching, that depends on closed continuous polygons is not
        # done correctly. This is why they are not used, and we depend fully on _clip_mpl function.
        # Do NOT use simplify on path.cleaned, it produces strange vertices at 0, 0
        bbox = gc.get_clip_rectangle()
        path = path.cleaned(transform=transform, remove_nans=True, simplify=False)
        if bbox is not None:
            clippoly = box(bbox.x0, bbox.y0, bbox.x1, bbox.y1)
        else:
            clippoly = None

        dxfattribs = self._get_polyline_attribs(gc)

        group_data = []
        if rgbFace is not None:
            hatch = self.modelspace.add_hatch(
                dxfattribs=get_color_attribs(rgbFace)
            )
            self.set_entity_attribs(gc, hatch)
            group_data.append(hatch)
        else:
            hatch = None

        for vertices in path.to_polygons(closed_only=False):
            if clippoly is not None:
                vertices = self._clip_mpl(vertices, clippoly)
                if vertices is None:
                    continue
            close = (rgbFace is not None) or (len(vertices) > 1 and np.array_equal(vertices[0], vertices[-1]))
            poly = self.modelspace.add_lwpolyline(points=vertices,
                                                  close=close,
                                                  dxfattribs=dxfattribs)
            poly.set_flag_state(128, True)
            self.set_entity_attribs(gc, poly)

            if rgbFace is not None:
                hpath = hatch.paths.add_polyline_path(
                    poly.get_points(format='xyb'),
                    is_closed=True)
                hatch.associate(hpath, [poly])
            self._draw_mpl_hatch(gc, path, poly, group_data=group_data)

            if group_data:
                group = self.drawing.groups.new()
                group.set_data(group_data)
        return

        # hpath = gc.get_hatch_path()
        # if HATCH_LINES_DRAW_AS_PAT and hpath is not None:
        #     def hatch_as_pat():
        #         hatch_name = gc.get_hatch()
        #         if hatch_name == "'": return
        #         ext = path.get_extents(transform=transform)
        #         if (ext.x0 < 0 or ext.x0 > self.width) and (ext.x1 < 0 or ext.x1 > self.width):
        #             return
        #         if (ext.y0 < 0 or ext.y0 > self.height) and (ext.y1 < 0 or ext.y1 > self.height):
        #             return
        #
        #         patterns = []
        #         cx, cy = 0.5 * (ext.x1 + ext.x0), 0.5 * (ext.y1 + ext.y0)
        #         _transform = Affine2D().translate(-0.5, -0.5).scale(self.dpi).translate(cx, cy)
        #         hpatht = hpath.transformed(_transform)  # needs clipping
        #         _path = hpatht.to_polygons(closed_only=False)
        #
        #         for vertices in _path:
        #             if np.array_equal(vertices[0], vertices[-1]):
        #                 continue
        #             vertices *= 0.01
        #             for p0, p1 in pairwise(vertices):
        #                 pattern = hatchmakerSSIO(p0, p1, dxf_mode=True, return_as_string=False)
        #                 patterns.append(pattern)
        #
        #         patterns = [list(d.values()) for d in patterns]
        #         if not patterns:
        #             return
        #
        #         hatch = self.modelspace.add_hatch(
        #             dxfattribs=get_color_attribs(gc.get_hatch_color()) | {
        #                 'lineweight': self.points_to_pixels(gc.get_hatch_linewidth()) * 10 * 2}
        #         )
        #         self.set_entity_attribs(gc, hatch)
        #         pat_title = clean_pat_title(hatch_name)
        #         hatch.set_pattern_fill(
        #             name=f'mpl_{pat_title}',
        #             scale=100 * HATCH_SCALE_FACTOR,
        #             definition=patterns,
        #         )
        #         hpath_ = hatch.paths.add_polyline_path(
        #             # get path vertices from associated LWPOLYLINE entity
        #             poly.get_points(format='xyb'),
        #             # get closed state also from associated LWPOLYLINE entity
        #             is_closed=poly.closed)
        #         hatch.associate(hpath_, [poly])
        #
        #     hatch_as_pat()

    def _draw_mpl_hatch(self, gc, path, pline, group_data=None):
        '''Draw MPL hatch
        '''
        hatch = gc.get_hatch()
        if hatch is not None:
            def draw(shape):
                if hasattr(shape, 'exterior'):
                    is_poly = True
                    clipped = shape.exterior.coords
                else:
                    is_poly = False
                    clipped = shape.coords
                if clipped:
                    if is_poly:
                        entity = self.modelspace.add_hatch(dxfattribs=get_color_attribs(rgb))
                        entity.paths.add_polyline_path(clipped, is_closed=True)
                    else:
                        entity = self.modelspace.add_lwpolyline(points=clipped,
                                                                dxfattribs=get_color_attribs(rgb) | {
                                                                    'lineweight': gc._hatch_lineweight}
                                                                )
                        entity.set_flag_state(128, True)
                    if group_data is not None:
                        group_data.append(entity)

            # find extents and center of the original unclipped parent path
            ext = path.get_extents()
            dx = ext.x1 - ext.x0
            cx = 0.5 * (ext.x1 + ext.x0)
            dy = ext.y1 - ext.y0
            cy = 0.5 * (ext.y1 + ext.y0)

            # matplotlib uses a 1-inch square hatch, so find out how many rows
            # and columns will be needed to fill the parent path
            rows, cols = math.ceil(dy / (self.dpi * HATCH_SCALE_FACTOR)) - 1, math.ceil(
                dx / (self.dpi * HATCH_SCALE_FACTOR)) - 1
            # get color of the hatch
            rgb = gc.get_hatch_color()

            # get hatch paths
            hpath = gc.get_hatch_path()

            # this is a tranform that produces a properly scaled hatch in the center
            # of the parent hatch
            _transform = Affine2D().translate(-0.5, -0.5).scale(self.dpi * HATCH_SCALE_FACTOR).translate(cx, cy)
            hpatht = hpath.transformed(_transform)

            # print("\tHatch Path:", hpatht)
            # now place the hatch to cover the parent path
            for irow in range(-rows, rows + 1):
                for icol in range(-cols, cols + 1):
                    # transformation from the center of the parent path
                    _trans = Affine2D().translate(icol * self.dpi * HATCH_SCALE_FACTOR,
                                                  irow * self.dpi * HATCH_SCALE_FACTOR)
                    # transformed hatch
                    _hpath = hpatht.transformed(_trans)

                    # turn into list of vertices to make up polygon
                    _path = _hpath.to_polygons(closed_only=HATCH_LINES_DRAW_AS_PAT)

                    for vertices in _path:
                        # clip each set to the parent path
                        if len(vertices) < 2:
                            continue
                        vertices_is_closed = np.array_equal(vertices[0], vertices[-1])
                        try:
                            clippoly = Polygon(pline.vertices())
                        except ValueError:
                            # when not enough points for Polygon
                            continue
                        if vertices_is_closed:
                            shape = Polygon(vertices)
                        else:
                            shape = LineString(vertices)
                        if not shape.is_valid:
                            continue
                        if not clippoly.contains(shape) and not clippoly.intersects(shape):
                            # ignore shape when shape is completely outside clippoly,
                            # prevents intersection invalid warning
                            continue
                        if shape.is_simple:
                            try:
                                shape = shape.intersection(clippoly)
                            except GEOSException as e:
                                continue
                        if shape.geom_type in ['Polygon', 'LineString']:
                            draw(shape)
                        elif shape.geom_type == 'MultiPolygon':
                            for shape_ in list(shape.geoms):
                                draw(shape_)
                        else:
                            pass

    def draw_path(self, gc, path, transform, rgbFace=None):
        # print('\nEntered ###DRAW_PATH###')
        # print('\t', self._groupd)
        # print('\t', gc.__dict__, rgbFace)
        # print('\t', gc.get_sketch_params())
        # print('\tMain Path', path.__dict__)
        # hatch = gc.get_hatch()
        # if hatch is not None:
        #     print('\tHatch Path', gc.get_hatch_path().__dict__)
        self.check_gc(gc)
        self._draw_mpl_patch(gc, path, transform, rgbFace, obj=self._groupd[-1])

    def draw_image(self, gc, x, y, im, transform=None):
        pass

    def draw_text(self, gc, x, y, s, prop, angle, ismath=False, mtext=None):
        # print('DXF draw_text', s)
        # print(x * 72 / 100, y * 72 / 100, s, mtext)
        # print(prop.__dict__)
        # print(dir(prop))
        # print(s)
        props = ['get_family', 'get_file', 'get_fontconfig_pattern', 'get_math_fontfamily', 'get_name', 'get_size',
                 'get_size_in_points', 'get_slant', 'get_stretch', 'get_style', 'get_variant', 'get_weight']
        # for prop_ in props:
        #     print(prop_, getattr(prop, prop_)())
        # print(s)
        # print(dir(gc))
        # print(dir(prop))
        # if mtext is not None:
        #     print(dir(mtext))
        self.check_gc(gc)
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
        fontname = os.path.basename(font_manager.findfont(prop))
        # s = s.replace(u"\u2212", "-")
        s.encode('ascii', 'ignore').decode()
        text = self.modelspace.add_text(s, height=fontsize, rotation=angle, dxfattribs={
            **get_color_attribs(gc.get_rgb()),
            'style': fontname,
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

    # def points_to_pixels(self, points):
    #     return points / 72.0 * self.dpi

    def get_text_width_height_descent(self, s, prop, ismath):
        font = self._get_font_ttf(prop)
        font.set_text(s, 0.0, flags=2)
        w, h = font.get_width_height()
        d = font.get_descent()
        scale = 1 / 64
        w *= scale * 0.72  # if changed to 0.72 text is correctly wraped only for horizontal lines
        h *= scale * 1
        d *= scale * 1
        # print('DXF', s, w, h, d)
        return w, h, d

    def _get_font_ttf(self, prop):
        fnames = font_manager.fontManager._find_fonts_by_props(prop)
        font = font_manager.get_font(fnames)
        font.clear()
        font.set_size(prop.get_size_in_points(), self.dpi)
        return font


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
        import io
        drawing = self.draw()
        if isinstance(filename, io.StringIO):
            drawing.write(filename)
        else:
            drawing.saveas(filename)

    def get_default_filetype(self):
        return 'dxf'


@_Backend.export
class _BackendDXF(_Backend):
    FigureCanvas = FigureCanvasDXF
    FigureManagerDXF = FigureManagerBase
