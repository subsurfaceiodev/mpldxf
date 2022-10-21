import matplotlib.pyplot as plt
from scipy.special import sindg, cosdg

fig, ax = plt.subplots()
ax.grid()
s = '220.695531,0,0,56.72741639,0.01516370,0.39568169,-65.55126668'
angle, x, y, dx, dy, dash, space = [float(x) for x in s.split(',')]
sin_angle = sindg(angle)
cos_angle = cosdg(angle)
dash_x = dash * cos_angle
dash_y = dash * sin_angle
dash_plus_space = dash + -space
dash_plus_space_x = dash_plus_space * cos_angle
dash_plus_space_y = dash_plus_space * sin_angle
dy_x = dy * cosdg(angle + 90)
dy_y = dy * sindg(angle + 90)
dx_x = dx * cos_angle
dx_y = dx * sin_angle
dxy_x = dx_x + dy_x
dxy_y = -(dx_y + dy_y)
x_max = 1000


def plot_diagonal(x0, y0):
    for i in range(1000000):
        x_offset = dash_plus_space_x * i
        y_offset = dash_plus_space_y * i
        x0_ = x0 + x_offset
        y0_ = y0 + y_offset
        if not x_max > x0_ > - x_max:
            return
        x = [x0_, x0_ + dash_x]
        y = [y0_, y0_ + dash_y]
        ax.plot(x, y)


x0, y0 = (x, y)
for i in range(10000):
    plot_diagonal(x0 + dxy_x * i, y0 + dxy_y * i)
plt.show()
