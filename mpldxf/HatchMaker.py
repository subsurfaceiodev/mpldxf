import re
from warnings import warn
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

import ezdxf
import numpy as np

pi = np.pi


def rotate(p, origin=(0, 0), angle=0):
    # https://stackoverflow.com/questions/34372480/rotate-point-about-another-point-in-degrees-python
    # angle in radians
    R = np.array([[np.cos(angle), -np.sin(angle)],
                  [np.sin(angle), np.cos(angle)]])
    o = np.atleast_2d(origin)
    p = np.atleast_2d(p)
    return np.squeeze((R @ (p.T - o.T) + o.T).T)


PAT_UNITS_MAP = {'Millimeters': 'MM', 'Inches': 'INCH'}


def clean_pat_title(pat_title, software='AutoCAD'):
    if software == 'AutoCAD':
        pat_title = clean_special_characters(pat_title)
    return pat_title


def get_multiplier(value):
    multiplier = Fraction(value).limit_denominator(max_denominator=1000).denominator
    return multiplier


def get_angle_offsets(angle, round_precision=3):
    def integer_check(x, y):
        x_rounded = round(float(x), round_precision)
        y_rounded = round(float(y), round_precision)
        if x_rounded.is_integer() and y_rounded.is_integer():
            return x, y

    tan_angle = abs(np.tan(angle))  # check if abs is sufficient for  angles like 92 where value is negative!
    # tan_angle_rounded = round(float(tan_angle), 1)
    # angle = np.arctan(tan_angle_rounded)
    # tan_angle = tan_angle_rounded
    if tan_angle > 1.0e+5 or np.isclose(tan_angle, 0):
        dx, dy, d = 0, 1, 1
    elif np.isclose(tan_angle, 1):
        d = np.sqrt(2)
        dx = d / 2
        dy = -dx
    else:
        def method1():
            x = 1
            while True:
                y = x * tan_angle
                y_rounded = round(y, round_precision)
                if y_rounded.is_integer():
                    break
                x += 1
            return x, y

        def method2():
            # tan_angle = OPP / ADJ
            # if tan_angle > 1 then OPP > ADJ
            # if tan_angle < 1 then OPP < ADJ
            if tan_angle < 1:
                x = np.abs(1 / tan_angle)
                y = 1
                non_unit_var = x
            else:
                x = 1
                y = tan_angle
                non_unit_var = y
            checked = integer_check(x, y)
            if checked is not None:
                return checked
            else:
                multiplier = get_multiplier(non_unit_var)
                x_ = x * multiplier
                y_ = y * multiplier
                return x_, y_

        x, y = method2()
        d = np.sqrt(x ** 2 + y ** 2)
        tan_angle_sign = np.sign(np.tan(angle))
        dy = tan_angle_sign * 1 / d  # pending sign calculation

        def get_dx(angle, dy):
            dy_line_equation_y_intercept = dy / abs(np.cos(angle))

            # dy line equation
            def dy_line_equation(x):
                y = tan_angle * x + dy_line_equation_y_intercept
                # print(angle, x, dy_line_equation_y_intercept, tan_angle, y)
                return y

            x_ = 0
            while True:
                y_ = dy_line_equation(x_)
                checked = integer_check(x_, y_)
                if x_ > 5000:
                    raise StopIteration('max iter reached')
                elif checked is None:
                    x_ += 1
                else:
                    d_ = np.sqrt(x_ ** 2 + (y_ - dy_line_equation_y_intercept) ** 2)
                    d__ = dy * tan_angle
                    dx = d_ + d__
                    return dx

        dx = get_dx(angle, abs(dy))

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
            try:
                dx, dy, d = get_angle_offsets(angle)
            except StopIteration:
                warn(f'line with {angle=} {x=} {y=} reached maximum iterations')
                continue
            space = d - dash
            hatch_lines.append(HatchLine(
                np.rad2deg(angle), x, y, dx, dy, dash, -space
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
