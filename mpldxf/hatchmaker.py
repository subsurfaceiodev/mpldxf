import re
from timeit import default_timer
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable
import logging
from sympy.solvers.diophantine.diophantine import diop_linear
from sympy.core.containers import Tuple
from sympy import symbols, nsimplify
import io
import ezdxf
import numpy as np
import pandas as pd
from math import lcm, gcd
from itertools import pairwise

pi = np.pi
PAT_UNITS_MAP = {'Millimeters': 'MM', 'Inches': 'INCH'}
logging.basicConfig(level=logging.WARNING)  # set to DEBUG for debugging


def rotate(p, origin=(0, 0), angle=0):
    # https://stackoverflow.com/questions/34372480/rotate-point-about-another-point-in-degrees-python
    # angle in radians
    R = np.array([[np.cos(angle), -np.sin(angle)],
                  [np.sin(angle), np.cos(angle)]])
    o = np.atleast_2d(origin)
    p = np.atleast_2d(p)
    return np.squeeze((R @ (p.T - o.T) + o.T).T)


def clean_pat_title(pat_title, software='AutoCAD'):
    if software == 'AutoCAD':
        pat_title = clean_special_characters(pat_title)
    return pat_title


def float_to_fraction(
        value,
        round_decimals,
):
    multiplier = Fraction(value).limit_denominator(max_denominator=10 ** round_decimals)
    return multiplier


def clean_special_characters(string):
    return re.sub('\\W+', '', string)


def get_clockwise_angle(x_distance, y_distance):
    # angle in radians
    angle = np.arctan2(y_distance, x_distance)
    angle[angle < 0] = 2 * pi + angle[angle < 0]
    return angle


def get_angle_offsets(
        angle,
        round_decimals=4,
        canvas_width=1.0,
        canvas_height=1.0,
):
    angle_degrees = np.rad2deg(angle)
    tan_angle = np.tan(angle)
    tan_angle_abs = abs(tan_angle)

    canvas_ratio = canvas_height / canvas_width

    logging.debug(f'Calculation started for {angle_degrees=} {tan_angle=}')
    if tan_angle_abs > 1.0e+5:
        logging.debug('vertical line')
        dx, dy, d = 0, canvas_width, canvas_height
    elif np.isclose(tan_angle_abs, 0):
        logging.debug('horizontal line')
        dx, dy, d = 0, canvas_height, canvas_width
    elif np.isclose(tan_angle_abs, 1) and np.isclose(canvas_ratio, 1):
        logging.debug('45 degrees line')
        d = np.sqrt(canvas_width ** 2 + canvas_height ** 2)
        dx = d / 2
        dy = -dx
    else:
        tan_angle_abs_fraction = float_to_fraction(tan_angle_abs, round_decimals=round_decimals)
        # TODO decide if angle_corrected should go to actual pat definition instead of
        #  angle, similar to pattycake
        angle_corrected = np.arctan(float(tan_angle_abs_fraction))
        angle_corrected_degrees = np.rad2deg(angle_corrected)
        logging.debug(f'line at {angle_corrected_degrees=} {tan_angle_abs_fraction=}')

        def line_equation_handler(c=0, solve_at=1):
            method = 'ssio'
            # line_equation: y = mx + b
            # linear diophantine equation: ax + by = c
            a = canvas_width * tan_angle_abs_fraction
            b = canvas_height
            c = c
            x, y, t = symbols('x, y, t_0', integer=True)
            diophantine_solution = None

            start_time = default_timer()
            if method == 'sympy':
                # this method is slow, was created mainly to validate ssio method
                line_equation = a * x + c - b * y
                # convert all floats to fractions:
                line_equation_rational = nsimplify(line_equation, rational=True, tolerance=0.00001)
                # convert all coefficients to integers from the
                # least common multiple of fraction denominators
                line_equation_integer_fraction = line_equation_rational.as_numer_denom()
                line_equation_lcm = line_equation_integer_fraction[1]
                line_equation_integer = line_equation_integer_fraction[0]
            elif method == 'ssio':
                line_equation = f'{a} * x - {b} * y'
                a_rational = float_to_fraction(a, 5)
                b_rational = float_to_fraction(b, 5)
                c_rational = float_to_fraction(c, 5)
                line_equation_rational = f'{a_rational} * x - {b_rational} * y'
                line_equation_lcm = lcm(
                    a_rational.denominator,
                    b_rational.denominator,
                    c_rational.denominator
                )
                a_int = line_equation_lcm * a_rational
                b_int = line_equation_lcm * b_rational
                c_int = line_equation_lcm * c_rational
                line_equation_integer = a_int * x - b_int * y
                if c == 0:
                    # Homogeneous Linear Diophantine equation (HLDE)
                    # this section is for slight speed up when applicable
                    gcd_ = gcd(int(a_int), int(b_int))
                    x_int, y_int = b_int / gcd_, a_int / gcd_
                    diophantine_solution = Tuple(x_int * t, y_int * t)
                else:
                    # Linear Diophantine equation (LDE)
                    line_equation += f' + {c}'
                    line_equation_rational += f' + {c_rational}'
                    line_equation_integer += c_int
            else:
                raise Exception(f'{method=} not valid')

            # from https://en.wikipedia.org/wiki/Diophantine_equation:
            # Finding all right triangles with integer side-lengths is
            # equivalent to solving the Diophantine equation
            if diophantine_solution is None:
                diophantine_solution = diop_linear(line_equation_integer)

            execution_time = default_timer() - start_time
            logging.debug(f'{execution_time=}')
            logging.debug(
                f'{line_equation=}, {line_equation_rational=}, {line_equation_lcm=}, {line_equation_integer=}, {diophantine_solution=}')
            if diophantine_solution == (None, None):
                raise Exception('solution not possible')
            x_int, y_int = diophantine_solution.subs({t: solve_at})
            logging.debug(f'{x_int=} {y_int=}')
            if x_int == 0 and y_int == 0:
                raise Exception('solution not possible')
            x_float, y_float = float(x_int * canvas_width), float(y_int * canvas_height)
            d = np.sqrt(x_float ** 2 + (y_float - c) ** 2)
            logging.debug(f'{x_float=} {y_float=} {d=}')
            return x_float, y_float, d

        canvas_factor = canvas_width * canvas_height
        _, _, d = line_equation_handler()
        tan_angle_sign = np.sign(tan_angle)
        dy = tan_angle_sign * canvas_factor / d

        def get_dx(
                dy,
        ):
            c = dy / abs(np.cos(angle_corrected))
            x, y, d = line_equation_handler(c, solve_at=0)
            if x != 0:
                dy *= np.sign(x)
            d__ = dy * tan_angle_abs_fraction
            dx = d + d__
            return dx, dy

        dx, dy = get_dx(
            dy
        )
        dy *= tan_angle_sign
    return dx, dy, d


@dataclass
class HatchLine:
    angle: float
    x: float
    y: float
    shift: float
    offset: float
    dash: float
    space: float

    def to_str(self):
        data = [
            f'{x:.6f}' if i == 0 else f'{x:.8f}'
            for i, x in enumerate(self.__dict__.values())
        ]
        data_str = ','.join(data)
        return data_str

    def get_ezdxf_definition(self):
        shift, offset = rotate(
            (self.shift, self.offset), angle=np.deg2rad(self.angle)
        )
        return [self.angle, (self.x, self.y), (shift, offset), [self.dash, self.space]]


@dataclass
class HatchMaker:
    hatch_lines: Iterable[HatchLine] = None
    pat_title: str = 'title'
    pat_description: str = 'description'
    pat_software: str = 'AutoCAD'
    pat_units: str = 'Millimeters'
    pat_type: str = 'Model'

    def __post_init__(self):
        self.pat_title_safe = clean_pat_title(self.pat_title, software=self.pat_software)

    @staticmethod
    def read_pat_str_as_df(pat_str):
        # useful for testing
        s_ = []
        for x in pat_str.splitlines():
            if x == '' or x.startswith((';', '*')) or x == '\n':
                continue
            s_.append(x)
        s_ = '\n'.join(s_)

        df = pd.read_csv(
            io.StringIO(s_),
            skipinitialspace=True,
            header=None,
        )
        df.columns = ['angle', 'x', 'y', 'shift', 'offset', 'dash', 'space'][:len(df.columns)]
        return df

    @staticmethod
    def read_pat_as_df(path):
        # useful for testing
        with open(path, 'r') as f:
            pat_str = f.read()
        df = HatchMaker.read_pat_str_as_df(
            pat_str
        )
        return df

    @staticmethod
    def df_to_points(df, return_as_df=False):
        # useful for testing
        df = df.rename(columns={'x': 'x0', 'y': 'y0'})
        df['x1'] = df['x0'] + df['dash'] * np.cos(np.deg2rad(df['angle']))
        df['y1'] = df['y0'] + df['dash'] * np.sin(np.deg2rad(df['angle']))
        if return_as_df:
            return df
        p0 = list(zip(df['x0'], df['y0']))
        p1 = list(zip(df['x1'], df['y1']))
        return p0, p1

    def set_from_frame(
            self,
            frame,
            round_decimals=4,
            canvas_width=1.0,
            canvas_height=1.0,
    ):
        p0 = list(zip(frame['x0'], frame['y0']))
        p1 = list(zip(frame['x1'], frame['y1']))
        self.set_from_points(
            p0,
            p1,
            round_decimals,
            canvas_width,
            canvas_height,
        )
        return self

    @staticmethod
    def polylines_to_points(
            polylines
    ):
        p0_all = []
        p1_all = []
        for p0, p1 in pairwise(polylines):
            p0_all.append(p0)
            p1_all.append(p1)
        return p0_all, p1_all

    @staticmethod
    def polylines_list_to_points(
            polylines_list
    ):
        p0_all = []
        p1_all = []
        for polylines in polylines_list:
            p0, p1 = HatchMaker.polylines_to_points(polylines)
            p0_all.extend(p0)
            p1_all.extend(p1)
        return p0_all, p1_all

    def set_from_points(
            self,
            p0,
            p1,
            round_decimals=4,  # < 5 prevents invalid angles
            canvas_width=1.0,
            canvas_height=1.0,
    ):
        p0 = np.round(p0, round_decimals)
        p1 = np.round(p1, round_decimals)

        p0 = p0
        p1 = p1
        p0_x = p0[:, 0]
        p0_y = p0[:, 1]
        p1_x = p1[:, 0]
        p1_y = p1[:, 1]
        delta_x = p1_x - p0_x
        delta_y = p1_y - p0_y
        length = np.sqrt(delta_x ** 2 + delta_y ** 2)
        angle_to = get_clockwise_angle(delta_x, delta_y)

        hatch_lines = []
        for angle, x, y, dash in zip(
                angle_to,
                p0_x,
                p0_y,
                length,
        ):
            angle_degrees = np.rad2deg(angle)
            try:
                dx, dy, d = get_angle_offsets(
                    angle,
                    round_decimals=round_decimals,
                    canvas_width=canvas_width,
                    canvas_height=canvas_height,
                )
            except Exception as e:
                e.add_note(f'line with {angle_degrees=} {x=} {y=}')
                logging.exception(e)
                continue

            space = d - dash
            hatch_lines.append(HatchLine(
                angle_degrees, x, y, dx, dy, dash, -space
            ))

        self.hatch_lines = hatch_lines
        return self

    def to_pat(
            self,
            export_path=None,
    ):
        if self.pat_software == 'AutoCAD':
            pat_str = [
                f'*{self.pat_title_safe},{self.pat_description}',
                ';angle,x,y,shift,offset,dash,space',
            ]
        elif self.pat_software == 'Revit':
            pat_str = [
                f';%UNITS={PAT_UNITS_MAP[self.pat_units]}',
                f'*{self.pat_title_safe},{self.pat_description}',
                f';%TYPE={self.pat_type.upper()}',
                ';angle,x,y,shift,offset,dash,space',
            ]
        else:
            raise Exception(f'{self.pat_software=} not valid')

        for hatch_line in self.hatch_lines:
            pat_str.append(hatch_line.to_str())

        pat_str = '\n'.join(pat_str + [''])
        if export_path is not None:
            if isinstance(export_path, io.StringIO):
                file = export_path
            else:
                file = open(f'{export_path}/{self.pat_title}.pat', 'a')
            print(
                pat_str,
                file=file,
                end='',
            )
        return pat_str

    def to_dxf(
            self,
            export_path=None,
            doc=None,
            poly_x_offset=0,
            scale=1.0,
    ):
        # adapted from https://ezdxf.readthedocs.io/en/stable/tutorials/hatch_pattern.html#tut-hatch-pattern
        if doc is None:
            doc = ezdxf.new()
        msp = doc.modelspace()
        hatch = msp.add_hatch()
        hatch.set_pattern_fill(
            self.pat_title,
            color=7,
            angle=0,
            scale=scale,
            style=0,
            pattern_type=0,
            definition=[hatch_line.get_ezdxf_definition() for hatch_line in self.hatch_lines]
        )
        points = [(poly_x_offset, 0), (poly_x_offset + 10, 0), (poly_x_offset + 10, 10), (poly_x_offset, 10)]
        hatch.paths.add_polyline_path(points)
        msp.add_lwpolyline(points, close=True, dxfattribs={"color": 1})
        if export_path is not None:
            if isinstance(export_path, io.StringIO):
                file = export_path
                doc.write(file)
            else:
                file = f'{export_path}/{self.pat_title}.dxf'
                doc.saveas(file)
        return doc

    def to_dict(self):
        d = self.__dict__.copy()
        del d['pat_title_safe']
        d['hatch_lines'] = [hl.__dict__ for hl in d['hatch_lines']]
        return d

    @classmethod
    def from_dict(cls, d):
        d['hatch_lines'] = [HatchLine(**hl) for hl in d['hatch_lines']]
        return cls(**d)
