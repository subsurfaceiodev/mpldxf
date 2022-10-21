import numpy as np
from fractions import Fraction
from scipy.special import tandg
from mpldxf.HatchMaker import get_angle, data_to_string, rotate

def get_multiplier(value):
    multiplier = Fraction(value).limit_denominator(max_denominator=100).denominator
    return multiplier
# print(get_multiplier(1/tandg(30)))
# dfgdgh
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


def hatchmaker(p0, p1, dxf_mode=False, return_as_string=False, points_round_precision=3):
    locals_copy = {**locals()}
    DXF_MODE_FACTOR = 1
    p0, p1 = np.round(p0, points_round_precision), np.round(p1, points_round_precision)  # prevents invalid angles ?
    x_distance = p1[0] - p0[0]
    y_distance = p1[1] - p0[1]
    angle = get_angle(x_distance, y_distance)
    base_point = p0
    dash_solid_distance = np.sqrt(x_distance ** 2 + y_distance ** 2)
    try:
        base_point_x_offset, base_point_y_offset, d = get_angle_offsets(angle)
    except StopIteration:
        return hatchmaker(**locals_copy | dict(points_round_precision=2))
    dash_gap_distance = (d - dash_solid_distance)
    if dxf_mode:
        base_point_xy_offset_rotated = rotate(
            (base_point_x_offset * DXF_MODE_FACTOR, base_point_y_offset * DXF_MODE_FACTOR), angle=angle)
        args = dict(
            angle=np.rad2deg(angle),
            base_point=base_point * DXF_MODE_FACTOR,
            offset=base_point_xy_offset_rotated,
            dash_length_items=(dash_solid_distance * DXF_MODE_FACTOR, -dash_gap_distance * DXF_MODE_FACTOR),
        )
    else:
        args = dict(
            angle=np.rad2deg(angle),
            base_point=base_point,
            offset=(base_point_x_offset, base_point_y_offset),
            dash_length_items=(dash_solid_distance, -dash_gap_distance),
        )
    if return_as_string:
        args = data_to_string(args)
    return args


def test1():
    angle_ = 45 * 2
    angles = np.arange(angle_, angle_+90.5, 0.5)
    # angle_ = 30
    # angles = [angle_, 180-angle_]
    pt1 = (0, 0)
    for angle in angles:
        angle_rad = np.deg2rad(angle)
        pt2 = (0.1 * np.cos(angle_rad), 0.1 * np.sin(angle_rad))
        returned = hatchmaker(pt1, pt2, return_as_string=True)
        print(returned)


# test1()
# pt1 = [(0, 0), (0, 0), (0, 0)]
# pt2 = [(0, -0.1), (0, 0.1), (0.1, 0.1)]
# pt1 = [(2.2076/10, 6.5537/10),(2.2539/10, 6.3684/10)] # ,(2.2539/10, 6.3684/10)
# pt2 = [(2.0686/10, 6.5768/10),(2.2076/10, 6.5537/10)]
# pt1 = (0, 0)
# pt2 = (0.226225, 0.257925)
# print(hatchmaker(pt1, pt2, return_as_string=True))
