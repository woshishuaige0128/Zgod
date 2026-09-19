"""Rebuild Figure 2 as individually editable geometric primitives.

Coordinates follow the supplied 1672 x 941 reference raster.  All geometry and
text are native scene objects; the reference raster is never embedded.
"""

from pathlib import Path
from scene import Scene, BLUE


HERE = Path(__file__).resolve().parent
BLACK = '#080808'
LIGHT_GRAY = '#EFEFEF'
s = Scene(2, 1672, 941)


def text(name, x, y, w, h, content, size=43, color=BLACK, align='center'):
    s.text(name, x, y, w, h, content, size=size, color=color, align=align)


def dimension_vertical(name, x, y_top, y_bottom, label, label_y,
                       ext_start, ext_end, size=43):
    """Opposing inside arrowheads with a native text gap in the stem."""
    gap_top = label_y - 3
    gap_bottom = label_y + 50
    s.line(name + '_top_extension', ext_start, y_top, ext_end, y_top, BLUE, 2.7)
    s.line(name + '_bottom_extension', ext_start, y_bottom, ext_end, y_bottom, BLUE, 2.7)
    s.arrow(name + '_top', [[x, gap_top], [x, y_top + 3]], BLUE, 2.8, 22)
    s.arrow(name + '_bottom', [[x, gap_bottom], [x, y_bottom - 3]], BLUE, 2.8, 22)
    text(name + '_label', x - 48, label_y, 96, 52, label, size, BLUE)


def dimension_horizontal(name, x_left, x_right, y, label, label_x,
                         label_w=83, top=835, bottom=889):
    s.line(name + '_left_extension', x_left, top, x_left, bottom, BLUE, 2.7)
    s.line(name + '_right_extension', x_right, top, x_right, bottom, BLUE, 2.7)
    s.arrow(name + '_left', [[label_x - 6, y], [x_left + 2, y]], BLUE, 2.8, 22)
    s.arrow(name + '_right', [[label_x + label_w + 4, y], [x_right - 2, y]], BLUE, 2.8, 22)
    text(name + '_label', label_x, y - 24, label_w, 53, label, 43, BLUE)


def fixed_support(name, x, y):
    s.line(name + '_ground', x - 35, y, x + 37, y, BLACK, 3.3)
    for k in range(6):
        xx = x - 27 + 13 * k
        s.line(name + '_hatch_' + str(k + 1), xx, y + 1, xx - 15, y + 20, BLACK, 2.8)


def pinned_support(name, x, y):
    ground = y + 35
    s.path(name + '_triangle', [[x, y], [x - 21, ground], [x + 22, ground]], BLACK, 3.5, 'none', True)
    s.line(name + '_ground', x - 32, ground, x + 34, ground, BLACK, 3.3)
    for k in range(5):
        xx = x - 21 + 14 * k
        s.line(name + '_hatch_' + str(k + 1), xx, ground + 1, xx - 15, ground + 20, BLACK, 2.8)


# Reference frame: four columns, three floor beams and three equal bays.
text('reference_frame_heading', 349, 23, 458, 65, 'Reference frame', 53)
columns = [166, 433, 702, 968]
floors = [119, 341, 563]
for i, x in enumerate(columns):
    bottom = 778 if i in (0, 3) else 763
    s.line('column_' + str(i + 1), x, 119, x, bottom, BLACK, 7.0)
for i, y in enumerate(floors):
    s.line('floor_beam_' + str(3 - i), columns[0], y, columns[-1], y, BLACK, 6.7)

fixed_support('left_fixed_support', 166, 778)
pinned_support('first_internal_pinned_support', 433, 763)
pinned_support('second_internal_pinned_support', 702, 763)
fixed_support('right_fixed_support', 968, 778)

# Three explicit section designations, retained exactly as engineering text.
for i, y in enumerate([208, 430, 653]):
    text('column_designation_story_' + str(3 - i), 25, y, 124, 58,
         'W5×16', 40, align='left')

# Story dimensions.  The outer dimension line extends to the base of the frame.
dimension_vertical('height_story_3', 1047, 119, 341, '635', 211, 983, 1070)
dimension_vertical('height_story_2', 1047, 341, 564, '635', 433, 983, 1070)
dimension_vertical('height_story_1', 1047, 564, 779, '635', 653, 1016, 1070)

# Shared extension lines and the separate 762 dimensions below the three bays.
# Shared extension strokes deliberately occur only once, avoiding doubled lines.
for i, x in enumerate([164, 433, 703, 970]):
    s.line('bay_dimension_extension_' + str(i + 1), x, 835, x, 889, BLUE, 2.7)
for i, (x0, x1, label_x) in enumerate([(164, 433, 258), (433, 703, 530), (703, 970, 801)]):
    label_w = 77
    s.arrow('bay_' + str(i + 1) + '_left', [[label_x - 3, 867], [x0 + 2, 867]], BLUE, 2.8, 22)
    s.arrow('bay_' + str(i + 1) + '_right', [[label_x + label_w + 4, 867], [x1 - 2, 867]], BLUE, 2.8, 22)
    text('bay_' + str(i + 1) + '_label', label_x, 841, label_w, 58, '762', 43, BLUE)

# Beam I section: one closed editable contour with a light gray fill.
# The left dimension spans the full top-to-bottom outline (50), not clear web.
x_left, x_right = 1256, 1550
y_top, y_top_inner, y_bottom_inner, y_bottom = 276, 318, 618, 659
web_left, web_right = 1384, 1423
s.path('beam_I_section_outline', [
    [x_left, y_top], [x_right, y_top], [x_right, y_top_inner],
    [web_right, y_top_inner], [web_right, y_bottom_inner],
    [x_right, y_bottom_inner], [x_right, y_bottom], [x_left, y_bottom],
    [x_left, y_bottom_inner], [web_left, y_bottom_inner],
    [web_left, y_top_inner], [x_left, y_top_inner]
], BLACK, 4.2, LIGHT_GRAY, True)

# Flange width 38: the whole dimension stem is drawn below its label.
s.line('section_width_left_extension', x_left, 197, x_left, 251, BLUE, 2.8)
s.line('section_width_right_extension', x_right, 197, x_right, 251, BLUE, 2.8)
s.arrow('section_width_dimension', [[x_left + 2, 216], [x_right - 2, 216]], BLUE, 2.8, 22, both=True)
text('section_width_label', 1360, 165, 69, 53, '38', 41)

dimension_vertical('section_total_height', 1200, y_top, y_bottom, '50', 436,
                   1182, 1237, size=43)

# Top flange thickness 6, with arrows outside the closely spaced faces.
s.line('flange_thickness_top_extension', 1569, y_top, 1621, y_top, BLUE, 2.7)
s.line('flange_thickness_bottom_extension', 1569, y_top_inner, 1621, y_top_inner, BLUE, 2.7)
s.line('flange_thickness_stem', 1602, y_top, 1602, y_top_inner, BLUE, 2.7)
s.arrow('flange_thickness_upper', [[1602, 240], [1602, y_top - 1]], BLUE, 2.7, 21)
s.arrow('flange_thickness_lower', [[1602, 354], [1602, y_top_inner + 1]], BLUE, 2.7, 21)
text('flange_thickness_label', 1624, 272, 33, 56, '6', 43)

# Web thickness 6: two outside horizontal arrows point to the web faces.
s.arrow('web_thickness_left', [[1341, 472], [web_left - 2, 472]], BLUE, 2.8, 21)
s.arrow('web_thickness_right', [[1486, 472], [web_right + 2, 472]], BLUE, 2.8, 21)
text('web_thickness_label', 1498, 442, 35, 56, '6', 43)
text('beam_I_section_heading', 1222, 712, 359, 66, 'Beam I section', 51)

assert len(columns) == 4 and len(floors) == 3
assert y_top == 276 and y_bottom == 659
assert not any(obj['kind'] in ('image', 'svg', 'bitmap') for obj in s.objects)
assert len({obj['name'] for obj in s.objects}) == len(s.objects)
s.save(HERE / 'fig2.json')
print(f'Figure 2 saved: {len(s.objects)} native objects; 50 dimension spans y={y_top}..{y_bottom}.')

