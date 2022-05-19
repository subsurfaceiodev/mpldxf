"""
A backend to export DXF using a custom DXF renderer.

This allows saving of DXF figures.

Use as a matplotlib external backend:

  import matplotlib
  matplotlib.use('module://mpldxf.backend_dxf')

or register:

  matplotlib.backend_bases.register_backend('dxf', FigureCanvasDxf)

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
import os
import sys
import math

import matplotlib
from matplotlib.backend_bases import (RendererBase, FigureCanvasBase,
                                      GraphicsContextBase)
from matplotlib.transforms import Affine2D
import matplotlib.transforms as transforms
import matplotlib.collections as mplc
import numpy as np
import ezdxf

from . import dxf_colors

# When packaged with py2exe ezdxf has issues finding its templates
# We tell it where to find them using this.
# Note we also need to make sure they get packaged by adding them to the
# configuration in setup.py
if hasattr(sys, 'frozen'):
    ezdxf.options.template_dir = os.path.dirname(sys.executable)


def rgb_to_dxf(rgb_val):
    """Convert an RGB[A] colour to DXF colour index.

       ``rgb_val`` should be a tuple of values in range 0.0 - 1.0. Any
       alpha value is ignored.
    """
    if rgb_val is None:
        dxfcolor = dxf_colors.WHITE
    # change black to white
    elif np.allclose(np.array(rgb_val[:3]), np.zeros(3)):
        dxfcolor = dxf_colors.nearest_index([255,255,255])
    else:
        dxfcolor = dxf_colors.nearest_index([255.0 * val for val in rgb_val[:3]])
    return dxfcolor

def converttodef(path):
    return [
        [
            228.0127875,
            (18.288, 25.4),
            (-203.200000016, -228.5999999858),
            [3.4172144, -338.3048363956],
        ]]
    linedef = list()
    pt0, pt1 = None, None
    pastcode = 0

    for vert, code in path.iter_segments():
        print(vert, code)
        
    for vert, code in path.iter_segments():
        # print(vert, code, pastcode)
        #starting vertix
        if (code == 2) | (code == 79):# | ((code == 1) & (pastcode != 0)):
            pt1 = vert
            
    #     if (~(pt0 is None) & ~(pt1 is None)):
    #     if pt0 and pt1:
    #         print(pt0, pt1)
            dy = pt1[1] - pt0[1]
            dx = pt1[0] - pt0[0]
            angle = np.degrees(np.arctan2(dy, dx))
            angle = 0.0
            basept = pt0
            offset = (dx, dy)
            dash = [100,-100]
            
            linedef.append([angle, basept, offset, dash])

            pt0 = pt1
        
            # if (code == 2):
            #     pt0 = pt1
            # if code == 79:
            #     return linedef
        elif code == 1:
            pt0 = vert

        if (code == 79) | ((code == 1) & (pastcode != 0)):
            return linedef

        pastcode = code

    return linedef


class RendererDxf(RendererBase):
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

    def _init_drawing(self):
        """Create a drawing, set some global information and add
           the layers we need.
        """
        drawing = ezdxf.new(dxfversion=self.dxfversion)
        modelspace = drawing.modelspace()
        drawing.header['$EXTMIN'] = (0, 0, 0)
        drawing.header['$EXTMAX'] = (self.width, self.height, 0)
        self.drawing = drawing
        self.modelspace = modelspace

    def clear(self):
        """Reset the renderer."""
        super(RendererDxf, self).clear()
        self._init_drawing()

    def _draw_path(self, vertices, **kwargs): 
        # A non-filled polygon or a line - use LWPOLYLINE entity
        return self.modelspace.add_lwpolyline(points=vertices,
                                        **kwargs)

    def _draw_hatch(self, vertices, **kwargs): 
        # A non-filled polygon or a line - use LWPOLYLINE entity
        hatch = self.modelspace.add_hatch(**kwargs)
        line = hatch.paths.add_polyline_path(vertices)
        return hatch, line

    def draw_path(self, gc, path, transform, rgbFace=None):
        """Draw a path.

           To do this we need to decide which DXF entity is most appropriate
           for the path. We choose from lwpolylines or hatches.
        """
        
        _ppath = path.transformed(transform)
        ppath = _ppath.to_polygons(closed_only=False) 
        for vertices in ppath:
            if rgbFace is not None and vertices.shape[0] > 2:
                # we have a face color so we draw a filled polygon,
                # in DXF this means a HATCH entity
                dxfcolor = rgb_to_dxf(rgbFace)
                hatch, _ = self._draw_hatch(vertices=vertices,
                        color=dxfcolor)
            else:
                # A non-filled polygon or a line - use LWPOLYLINE entity
                attrs = {'color': rgb_to_dxf(gc.get_rgb())}
                pline = self._draw_path(vertices=vertices,
                                   dxfattribs=attrs)


        # now deal with a hatch if exists
        hatch = gc.get_hatch()
        if hatch is not None:
            # find extents and center of the parent path
            ext = path.get_extents(transform=transform)
            dx = ext.x1-ext.x0
            cx = 0.5*(ext.x1+ext.x0)
            dy = ext.y1-ext.y0
            cy = 0.5*(ext.y1+ext.y0)

            # matplotlib uses a 1-inch square hatch, so find out how many rows
            # and columns will be needed to fill the parent path
            rows, cols = math.ceil(0.5*dy/self.dpi)-1, math.ceil(0.5*dx/self.dpi)-1

            # get color of the hatch
            rgb = gc.get_hatch_color()
            dxfcolor = rgb_to_dxf(rgb)

            # get hatch paths
            hpath = gc.get_hatch_path()

            # this is a tranform that produces a properly scaled hatch in the center
            # of the parent hatch
            _transform = Affine2D().translate(-0.5, -0.5).scale(self.dpi).translate(cx, cy)
            hpatht = hpath.transformed(_transform)

            # now place the hatch to cover the parent path
            for irow in range(-rows, rows+1):
                for icol in range(-cols, cols+1):
                    # transformation from the center of the parent path
                    _trans = Affine2D().translate(icol*self.dpi, irow*self.dpi)
                    # transformed hatch
                    _hpath = hpatht.transformed(_trans)

                    # turn into list of vertices to make up polygon
                    _path = _hpath.to_polygons(closed_only=False) 

                    for vertices in _path:
                        # clip each set to the parent path
                        # note that we expect some bad behavior clipping lines with a polygon
                        # and it will be delt with below
                        clipped = ezdxf.math.clip_polygon_2d(pline.vertices(), vertices)

                        # if there is something to plot
                        if len(clipped)>0:
                            if len(vertices) == 2:
                                # if the original path was a line sometimes the clipping algorithm
                                # gives back repeated vertices, so we'll remove the repeats here
                                clipped = [list(s) for s in list(dict.fromkeys([tuple(s) for s in clipped]))]
                                attrs = {'color': dxfcolor}
                                _line = self._draw_path(vertices=clipped,
                                                dxfattribs=attrs)
                            else:
                                hatch, _line = self._draw_hatch(vertices=clipped,
                                        color=dxfcolor)


    def draw_image(self, gc, x, y, im):
        pass

    def draw_text(self, gc, x, y, s, prop, angle, ismath=False, mtext=None):
        fontsize = self.points_to_pixels(prop.get_size_in_points())
        dxfcolor = rgb_to_dxf(gc.get_rgb())

        text = self.modelspace.add_text(s.encode('ascii', 'ignore').decode(), {
            'height': fontsize,
            'rotation': angle,
            'color': dxfcolor,
        })

        halign = self._map_align(mtext.get_ha(), vert=False)
        valign = self._map_align(mtext.get_va(), vert=True)
        align = valign
        if align:
            align += '_'
        align += halign

        # need to get original points for text anchoring
        pos = mtext.get_unitless_position()
        x, y = mtext.get_transform().transform(pos)

        p1 = x, y
        text.set_pos(p1, align=align)

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
            print(align)
            raise NotImplementedError
        if vert and align == 'CENTER':
            align = 'MIDDLE'
        return align

    def flipy(self):
        return False

    def get_canvas_width_height(self):
        return self.width, self.height

    def new_gc(self):
        return GraphicsContextBase()

    def points_to_pixels(self, points):
        return points / 72.0 * self.dpi


class FigureCanvasDxf(FigureCanvasBase):
    """
    A canvas to use the renderer. This only implements enough of the
    API to allow the export of DXF to file.
    """

    #: The DXF version to use. This can be set to another version
    #: supported by ezdxf if desired.
    DXFVERSION = 'AC1015'

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
            self.dxf_renderer = RendererDxf(w, h, self.figure.dpi,
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
    filetypes = FigureCanvasBase.filetypes.copy()
    filetypes['dxf'] = 'DXF'

    def print_dxf(self, filename, *args, **kwargs):
        """
        Write out a DXF file.
        """
        drawing = self.draw()
        drawing.saveas(filename)

    def get_default_filetype(self):
        return 'dxf'


########################################################################
#
# Now just provide the standard names that backend.__init__ is expecting
#
########################################################################

FigureCanvas = FigureCanvasDxf
