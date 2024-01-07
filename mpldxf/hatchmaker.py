import re
from warnings import warn
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

import io
import ezdxf
import numpy as np
import pandas as pd

pi = np.pi
PAT_UNITS_MAP = {'Millimeters': 'MM', 'Inches': 'INCH'}


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


def get_angle_offsets(
        angle,
        round_decimals=4,
        canvas_width=1,
        canvas_height=1,
        print_log=False,
):
    def integer_check(x, y):
        x_rounded = round(float(x), round_decimals)
        y_rounded = round(float(y), round_decimals)
        if x_rounded.is_integer() and y_rounded.is_integer():
            return x, y

    # seems to work as a rule of thumb
    if round_decimals > 4:
        dx_max_iterations = 50000
    else:
        dx_max_iterations = 5000

    angle_degrees = np.rad2deg(angle)
    tan_angle = np.tan(angle)
    tan_angle_abs = abs(tan_angle)

    canvas_ratio = canvas_height / canvas_width

    log = f'--------------\nCalculation started for {angle_degrees=} {tan_angle=}\n'

    if tan_angle_abs > 1.0e+5:
        # vertical line
        log += 'vertical line\n'
        dx, dy, d = 0, canvas_width, canvas_height
    elif np.isclose(tan_angle_abs, 0):
        # horizontal line
        log += 'horizontal line\n'
        dx, dy, d = 0, canvas_height, canvas_width
    elif np.isclose(tan_angle_abs, 1) and np.isclose(canvas_ratio, 1):
        log += '45 degrees line\n'
        d = np.sqrt(canvas_width ** 2 + canvas_height ** 2)
        dx = d / 2
        dy = -dx
    else:
        tan_angle_abs_fraction = float_to_fraction(tan_angle_abs, round_decimals=round_decimals)
        tan_angle_abs_numerator = tan_angle_abs_fraction.numerator
        tan_angle_abs_denominator = tan_angle_abs_fraction.denominator
        canvas_ratio_to_tan_angle_abs_ratio = canvas_ratio / tan_angle_abs

        log += f'line at angle {tan_angle_abs_fraction=}\n'

        def get_x_y():
            # tan_angle = OPP / ADJ
            # if tan_angle > 1 then OPP > ADJ
            # if tan_angle < 1 then OPP < ADJ
            multiplier = float_to_fraction(
                canvas_ratio_to_tan_angle_abs_ratio,
                round_decimals=round_decimals,
            ).denominator / tan_angle_abs_numerator * canvas_height
            x_ = tan_angle_abs_numerator * multiplier
            y_ = tan_angle_abs_denominator * multiplier
            return x_, y_

        canvas_factor = canvas_width * canvas_height
        x, y = get_x_y()
        d = np.sqrt(x ** 2 + y ** 2)
        log += f'{x=} {y=} {d=}'
        tan_angle_sign = np.sign(tan_angle)
        dy = tan_angle_sign * canvas_factor / d

        def get_dx(angle, dy):
            # TODO maybe its better to check if each point in iteration is multiple of base point?
            #  view asterisk guide
            #  one could get blue line equation and evaluate with x+basepointx
            #  also maybe use get_multiplier directly
            dy_line_equation_y_intercept = dy / abs(np.cos(angle))

            # dy line equation
            def dy_line_equation(x, b):
                y = tan_angle_abs * x + b
                # print(angle, x, dy_line_equation_y_intercept, tan_angle, y)
                return y

            x_ = 0
            while True:
                y_ = dy_line_equation(x_, b=dy_line_equation_y_intercept)
                checked = integer_check(x_ / canvas_width, y_ / canvas_height)
                y_dy_negative = y_ - dy_line_equation_y_intercept * 2
                checked_dy_negative = integer_check(x_ / canvas_width, y_dy_negative / canvas_height)
                if checked_dy_negative is not None:
                    # TODO for asterisk findings
                    y_ = y_dy_negative
                    dy = -dy
                    dy_line_equation_y_intercept *= -1
                    checked = checked_dy_negative
                if x_ > dx_max_iterations:
                    if print_log:
                        print(log)
                    raise StopIteration('max iter reached')
                elif checked is None:
                    x_ += canvas_width
                else:
                    from z3 import Ints, solve, Q
                    from decimal import Decimal
                    x, y = Ints('x y')
                    m = float_to_fraction(canvas_width * tan_angle_abs, round_decimals=round_decimals)
                    b = 1/4925
                    b = Q(1, 4925)
                    print(m)
                    m = Fraction(17.4 / 985).limit_denominator(10000)
                    print(m)
                    # m = 87/4925
                    # m = Q(87, 4925)
                    m = Q(m.numerator, m.denominator)
                    print(m)
                    print(Fraction(dy_line_equation_y_intercept).limit_denominator(100000))
                    # cwf = Product(174, canvas_width)
                    # cwf = round(174 * 0.1, 5)
                    solve(x >= 0, y >= 0, canvas_height * y == m * x + b)
                    # print('AAAAAAAAAAAAA')
                    # fraction_1 = Fraction(5000/dy_line_equation(5000, b=dy_line_equation_y_intercept)).limit_denominator(100)
                    # fraction_2 = Fraction(5000/dy_line_equation(5000, b=-dy_line_equation_y_intercept)).limit_denominator(100)
                    # # print(tan_angle_abs_fraction)
                    # print(fraction_1)
                    # print(fraction_2)
                    # x_at_y_equals_1_a = (1 - dy_line_equation_y_intercept) / tan_angle_abs
                    # x_at_y_equals_1_b = (1 - - dy_line_equation_y_intercept) / tan_angle_abs
                    # print(x_at_y_equals_1_a)
                    # print(x_at_y_equals_1_b)
                    # print(float_to_fraction(x_at_y_equals_1_a, round_decimals=round_decimals))
                    # print(float_to_fraction(x_at_y_equals_1_b, round_decimals=round_decimals))
                    print(f'{dy=} {tan_angle_abs=} {dy_line_equation_y_intercept=} {x_=} {y_=}')
                    # from sympy.solvers.diophantine.diophantine import diop_linear
                    # from sympy import symbols
                    #
                    # x, y, t = symbols('x, y, t_0', integer=True)
                    # print(f'{tan_angle_abs_numerator=}, {tan_angle_abs_denominator=}')
                    # try:
                    #     res = diop_linear(
                    #         tan_angle_abs_numerator * x -
                    #         tan_angle_abs_denominator * y + 1
                    #     )
                    #     print(res)
                    #     x__, y__ = res.subs({t: 0})
                    #     print(f'{canvas_width=} {canvas_height=}, {x_=} {x__=}, {y_=} {y__=}')
                    #     assert round(abs(x_), round_decimals) == abs(x__)
                    #     assert round(abs(y_), round_decimals) == abs(y__)
                    # except Exception as e:
                    #     print('Error!')

                    # print(dy / abs(np.sin(angle)))
                    d_ = np.sqrt(x_ ** 2 + (y_ - dy_line_equation_y_intercept) ** 2)
                    d__ = dy * tan_angle_abs
                    dx = d_ + d__
                    return dx, dy

        dx, dy = get_dx(angle, abs(dy))
        dy *= tan_angle_sign
    if print_log:
        print(log)
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
    def df_to_points(df):
        # useful for testing
        df = df.rename(columns={'x': 'x0', 'y': 'y0'})
        df['x1'] = df['x0'] + df['dash'] * np.cos(np.deg2rad(df['angle']))
        df['y1'] = df['y0'] + df['dash'] * np.sin(np.deg2rad(df['angle']))
        p0 = list(zip(df['x0'], df['y0']))
        p1 = list(zip(df['x1'], df['y1']))
        return p0, p1

    def set_from_frame(
            self,
            frame,
            round_decimals=4,
    ):
        p0 = list(zip(frame['x0'], frame['y0']))
        p1 = list(zip(frame['x1'], frame['y1']))
        self.set_from_points(
            p0,
            p1,
            round_decimals,
        )
        return self

    def set_from_points(
            self,
            p0,
            p1,
            round_decimals=4,  # < 5 prevents invalid angles
            canvas_width=1,
            canvas_height=1,
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
                    print_log=True,
                )
            except StopIteration:
                warn(f'line with {angle_degrees=} {x=} {y=} reached maximum iterations')
                continue
            space = d - dash
            hatch_lines.append(HatchLine(
                angle_degrees, x, y, dx, dy, dash, -space
            ))

        self.hatch_lines = hatch_lines
        return self

    def to_pat_str(
            self,
            pat_software='AutoCAD',
            pat_units='MM',
            pat_type='Model',
            export_path=None,
    ):
        if pat_software == 'AutoCAD':
            self.pat_title = clean_special_characters(self.pat_title)
            pat_str = [
                f'*{self.pat_title},{self.pat_description}',
                ';angle,x,y,shift,offset,dash,space',
            ]
        elif pat_software == 'Revit':
            pat_str = [
                f';%UNITS={PAT_UNITS_MAP[pat_units]}',
                f'*{self.pat_title},{self.pat_description}',
                f';%TYPE={pat_type.upper()}',
                ';angle,x,y,shift,offset,dash,space',
            ]
        else:
            raise Exception(f'{pat_software=} not valid')

        for hatch_line in self.hatch_lines:
            pat_str.append(hatch_line.to_str())

        pat_str = '\n'.join(pat_str + [''])
        if export_path is not None:
            print(
                pat_str,
                file=open(f'{export_path}/{self.pat_title}.pat', 'a'),
                end='',
            )
        return pat_str

    def to_dxf(
            self,
            doc=None,
            doc_save=True,
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
        if doc_save:
            doc.saveas(f'{self.pat_title}.dxf')


def clean_special_characters(string):
    return re.sub('\\W+', '', string)


def get_clockwise_angle(x_distance, y_distance):
    # angle in radians
    angle = np.arctan2(y_distance, x_distance)
    angle[angle < 0] = 2 * pi + angle[angle < 0]
    return angle


# print(HatchMaker().set_from_points([(0, 0)], [(2, 0.3)]))  # TODO
print(HatchMaker().set_from_points(
    [(0, 0)],
    # [(2, 5)],
    [(985, 174)],
    canvas_width=0.1,
    canvas_height=0.5,
))  # TODO