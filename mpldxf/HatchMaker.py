import numpy as np

pi = np.pi


def get_angle(x_distance, y_distance):
    angle = np.arctan2(y_distance, x_distance)
    if angle < 0:
        angle = 2 * pi + angle
    return angle


def rotate(p, origin=(0, 0), angle=0):
    # https://stackoverflow.com/questions/34372480/rotate-point-about-another-point-in-degrees-python
    R = np.array([[np.cos(angle), -np.sin(angle)],
                  [np.sin(angle), np.cos(angle)]])
    o = np.atleast_2d(origin)
    p = np.atleast_2d(p)
    return np.squeeze((R @ (p.T - o.T) + o.T).T)


def data_to_string(data):
    data_values = []
    for v in data.values():
        if not isinstance(v, (list, tuple, np.ndarray)):
            v = [v]
        data_values.extend(v)
    data_values = [f'{data_value:.6f}' if i == 0 else f'{data_value:.8f}' for i, data_value in
                   enumerate(data_values)]
    data_str = ','.join(data_values)
    return data_str


def hatchmaker_single(pt1, pt2, dxf_mode=False, return_as_data=False):
    pt1, pt2 = np.round(pt1, 3), np.round(pt2, 3)  # prevents invalid angles ?
    x_distance = pt2[0] - pt1[0]
    y_distance = pt2[1] - pt1[1]

    Dist = np.sqrt(x_distance ** 2 + y_distance ** 2)
    AngTo = get_angle(x_distance, y_distance)
    AngFrom = get_angle(-x_distance, -y_distance)
    IsValid = None

    if np.isclose(pt1[0], pt2[0], atol=0.0001) or np.isclose(pt1[1], pt2[1], atol=0.0001):
        DeltaX = 0
        DeltaY = 1
        Gap = Dist - 1
        IsValid = True
    else:
        Ang = AngTo if AngTo < pi else AngFrom
        AngZone = int(Ang / (pi / 4))
        XDir = abs(x_distance)
        YDir = abs(y_distance)
        Factor = 1
        RF = 1
        if AngZone == 0:
            DeltaY = abs(np.sin(Ang))
            DeltaX = abs(abs(1 / np.sin(Ang) - abs(np.cos(Ang))))
        elif AngZone == 1:
            DeltaY = abs(np.cos(Ang))
            DeltaX = abs(np.sin(Ang))
        elif AngZone == 2:
            DeltaY = abs(np.cos(Ang))
            DeltaX = abs(abs(1 / np.cos(Ang) - abs(np.sin(Ang))))
        elif AngZone == 3:
            DeltaY = abs(np.sin(Ang))
            DeltaX = abs(np.cos(Ang))
        if not np.isclose(XDir, YDir, atol=0.0001):  # 0.0001 instead of 0.001
            Ratio = YDir / XDir if XDir < YDir else XDir / YDir
            RF = Ratio * Factor
            Scaler = 1 / (XDir if XDir < YDir else YDir)
            if not np.isclose(Ratio, round(Ratio), atol=0.001):
                while Factor <= 100 and not np.isclose(RF, round(RF), atol=0.001):
                    Factor = Factor + 1
                    RF = Ratio * Factor
                if 1 < Factor <= 100:
                    _AB = XDir * Scaler * Factor
                    _BC = YDir * Scaler * Factor
                    _AC = np.sqrt(_AB ** 2 + _BC ** 2)
                    _EF = 1
                    x = 1
                    while x < (_AB - 0.5):
                        y = x * (YDir / XDir)
                        if Ang < pi / 2:
                            h = (1 + int(y)) - y
                        else:
                            h = y - int(y)
                        if h < _EF:
                            _AD = x
                            _DE = y
                            _AE = np.sqrt(x ** 2 + y ** 2)
                            _EF = h
                        x = x + 1
                    if _EF < 1:
                        _EH = (_BC * _EF) / _AC
                        _FH = (_AB * _EF) / _AC
                        DeltaX = _AE + (-_EH if Ang > (pi / 2) else _EH)
                        DeltaY = _FH
                        Gap = Dist - _AC
                        IsValid = True
        if Factor == 1:
            DeltaY = RF * DeltaY
            Gap = Dist - abs(Factor * (1 / DeltaY))
            IsValid = True  # revision pending
    if IsValid is True:
        if dxf_mode:
            DeltaX, DeltaY = rotate((DeltaX, DeltaY), angle=AngTo)
        data = dict(
            angle=np.rad2deg(AngTo),
            base_point=pt1,
            offset=(DeltaX, DeltaY),
            dash_length_items=(Dist, Gap),
        )
    else:
        # pt1, pt2 = np.round(pt1, 3), np.round(pt2, 3)  # prevents invalid angles ?
        # to_return = hatchmaker_single(pt1, pt2, dxf_mode=dxf_mode, return_as_data=return_as_data)
        # return to_return
        # warnings.warn(f'Invalid parameters {pt1}, {pt2}, {np.rad2deg(AngTo)}')
        data = None
    if return_as_data:
        return data
    else:
        if data is not None:
            strcat = data_to_string(data)
        else:
            strcat = None
        return strcat


def hatchmaker(pt1, pt2, dxf_mode=False, return_as_data=False, pat_header='pat_title,pat_description'):
    returned = []
    for pt1_, pt2_ in zip(pt1, pt2):
        returned_ = hatchmaker_single(pt1_, pt2_, dxf_mode=dxf_mode, return_as_data=return_as_data)
        if returned_ is not None:
            returned.append(returned_)
    if return_as_data:
        returned = returned
    else:
        returned = '\n'.join([f'*{pat_header}', *returned, ''])
    return returned


def test1():
    angles = np.arange(90, 92, 0.5)
    angles = [30, 92, 110]
    pt1 = (0, 0)
    for angle in angles:
        angle_rad = np.deg2rad(angle)
        pt2 = (0.1 * np.cos(angle_rad), 0.1 * np.sin(angle_rad))
        returned = hatchmaker_single(pt1, pt2, return_as_data=False)
        if returned is not None:
            print(returned)


# test1()
# pt1 = [(0, 0), (0, 0), (0, 0)]
# pt2 = [(0, -0.1), (0, 0.1), (0.1, 0.1)]
# pt1 = [(2.2076/10, 6.5537/10),(2.2539/10, 6.3684/10)] # ,(2.2539/10, 6.3684/10)
# pt2 = [(2.0686/10, 6.5768/10),(2.2076/10, 6.5537/10)]
# print(hatchmaker(pt1, pt2, return_as_data=False))
