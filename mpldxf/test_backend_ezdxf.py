"""Test the dxf matplotlib backend.

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
import matplotlib
import numpy as np
import os
import shutil
import tempfile
import unittest
from matplotlib import pyplot as plt
from numpy.random import random

from mpldxf import backend_dxf

matplotlib.backend_bases.register_backend('dxf',
                                          backend_dxf.FigureCanvas)


class DxfBackendTestCase(unittest.TestCase):
    """Tests for the dxf backend."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def setFig(self):
        fig, ax = plt.subplots(figsize=(15, 15))
        return fig, ax

    def tearDown(self):
        plt.clf()
        if os.path.isdir(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_plot(self):
        """Test a simple line with markers plot command."""
        fig, ax = self.setFig()
        ax.plot(range(5), [4, 3, 2, 1, 0], 'o-', label='data')
        ax.axvline(x=1)
        ax.axvspan(2, 3, zorder=-1, color='green')
        ax.legend()
        ax.set(xscale='log')
        outfile = os.path.join(self.test_dir, 'test_plot.dxf')
        fig.savefig(outfile)
        self.assertTrue(os.path.isfile(outfile))

    def test_boxplot(self):
        """Test a box-plot."""
        plt.boxplot(random((4, 30)))
        outfile = os.path.join(self.test_dir, 'test_boxplot.dxf')
        plt.savefig(outfile)
        self.assertTrue(os.path.isfile(outfile))

    def test_contour(self):
        """Test some contours."""
        plt.contour(random((30, 30)))
        outfile = os.path.join(self.test_dir, 'test_contour.dxf')
        plt.savefig(outfile)
        self.assertTrue(os.path.isfile(outfile))

    def test_contourf(self):
        """Test some filled contours."""
        plt.contourf(random((30, 30)))
        outfile = os.path.join(self.test_dir, 'test_contourf.dxf')
        plt.savefig(outfile)
        self.assertTrue(os.path.isfile(outfile))

    def test_bar(self):
        """Test a simple bar with hatches."""
        fig, ax = self.setFig()
        hatches = ['/', '\\', '|', '-', '+', 'x', 'o', 'O', '.', '*', '/o', '\\|', '|*', '-\\', '+o', 'x*', 'o-', 'O|',
                   'O.', '*-']
        colors = [*['none'] * len(hatches), *['cyan', 'blue', 'yellow', 'green', 'red'] * int(len(hatches) / 5)]
        ax.bar(
            x=[1] * len(hatches) + [2] * len(hatches),
            height=1,
            bottom=list(np.negative(range(len(hatches)))) * 2,
            hatch=hatches * 2,
            color=colors
        )
        outfile = os.path.join(self.test_dir, 'test_bar.dxf')
        fig.savefig(outfile)
        self.assertTrue(os.path.isfile(outfile))
