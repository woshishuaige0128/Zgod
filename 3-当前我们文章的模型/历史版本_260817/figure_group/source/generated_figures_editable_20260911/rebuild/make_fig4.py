"""Rebuild the approved generated Figure 4 with editable scene objects.

All coordinates are pixels on the 1254 x 1254 reference canvas.  The
generated reference determines member geometry.  The 2026-09-11 manuscript
determines the retained-coordinate colours; circled node identifiers are
black, including the reference image's red node identifiers 5 and 6.
"""
from pathlib import Path
import json
from collections import Counter

from scene import Scene, BLACK, BLUE, RED


s = Scene(4, 1254, 1254)
PALE_BLUE = '#EAF5FE'
PALE_CREAM = '#FDF2E6'
MEMBER_WIDTH = 2.65
ROTATION_WIDTH = 2.45


def line(name, x1, y1, x2, y2):
    s.line(name, x1, y1, x2, y2, BLACK, MEMBER_WIDTH)


def node(name, cx, cy, number):
    s.node(name, cx, cy, number, r=19.5, size=29, color=BLACK,
           fill='#FFFFFF')


def rotation(name, cx, y, index, retained=False):
    colour = RED if retained else BLACK
    s.rotation(name + '_arrow', cx, y, colour, r=19.5,
               width=ROTATION_WIDTH, head=10)
    s.psi(name + '_label', cx + 15, y + 12, index,
          size=29, color=colour, w=80)


def translation(name, x1, x2, y, index, retained=True):
    colour = RED if retained else BLACK
    s.arrow(name + '_arrow', [[x1, y], [x2, y]], colour,
            width=2.6, head=15)
    s.psi(name + '_label', x2 + 6, y - 23, index,
          size=32, color=colour, w=76)


def base(name, x, y, pinned):
    s.support(name, x, y, pinned=pinned, width=47, stroke=2.55)


# Background fields, sectional headings and addition signs.
for div, y0 in [('I', 45), ('II', 631)]:
    s.rect('division_' + div + '_numerical_panel', 31, y0, 712, 529,
           fill=PALE_BLUE, color='none', width=0, radius=13)
    s.rect('division_' + div + '_physical_panel', 795, y0, 430, 529,
           fill=PALE_CREAM, color='none', width=0, radius=13)
    s.text('division_' + div + '_numerical_title', 202, y0 + 8, 412, 43,
           'Numerical substructure', size=31, bold=True, align='center')
    s.text('division_' + div + '_physical_title', 840, y0 + 8, 342, 43,
           'Physical substructure', size=31, bold=True, align='center')
    s.text('division_' + div + '_addition', 749, y0 + 231, 40, 60,
           '+', size=50, bold=True, align='center')

s.text('division_I_label', 43, 0, 710, 43, '(a)  Division I',
       size=36, bold=True)
s.text('division_II_label', 41, 588, 710, 43, '(b) Division II',
       size=36, bold=True)

# Division I, numerical substructure.  The approved generated reference
# has a complete second-storey beam across its three bays.
for name, x, y1, y2 in [
    ('left_upper_column', 149, 141, 276),
    ('second_column', 300, 141, 406),
    ('third_column', 451, 141, 523),
    ('right_column', 606, 141, 532),
]:
    line('I_num_' + name, x, y1, x, y2)
for name, x1, x2, y in [
    ('third_storey_beam', 149, 606, 141),
    ('second_storey_beam', 149, 606, 276),
    ('first_storey_beam', 300, 606, 406),
]:
    line('I_num_' + name, x1, y, x2, y)
base('I_num_node3_pinned', 451, 523, True)
base('I_num_node4_fixed', 606, 532, False)

for num, cx, cy in [
    (13,129,115),(14,281,115),(15,433,115),(16,587,115),
    (9,122,249),(10,273,249),(11,426,249),(12,581,249),
    (6,273,377),(7,422,377),(8,578,377),
    (3,422,500),(4,577,500),
]:
    node('I_num_node' + str(num), cx, cy, num)
for y, items in [
    (141, [(149,12),(300,13),(451,14),(606,15)]),
    (276, [(149,7),(300,8),(451,9),(606,10)]),
    (406, [(300,3),(451,4),(606,5)]),
]:
    for x, index in items:
        rotation('I_num_psi' + str(index), x, y, index,
                 retained=index in {4,9,14})
for y, index in [(141,11),(276,6),(406,1)]:
    translation('I_num_psi' + str(index), 619, 671, y, index)

# Division I, physical substructure (outer bay, lower two storeys).
for x in [919,1065]:
    line('I_phys_column' + str(x), x, 240, x, 513 if x == 919 else 516)
for y in [240,373]:
    line('I_phys_beam' + str(y), 919, y, 1065, y)
base('I_phys_node1_fixed', 919, 513, False)
base('I_phys_node2_pinned', 1065, 516, True)
for num, cx, cy in [
    (9,896,217),(10,1045,215),(5,890,344),(6,1038,344),
    (1,890,488),(2,1040,488),
]:
    node('I_phys_node' + str(num), cx, cy, num)
for y, items in [(240,[(919,7),(1065,8)]), (373,[(919,2),(1065,3)])]:
    for x, index in items:
        rotation('I_phys_psi' + str(index), x, y, index)
for y, index in [(240,6),(373,1)]:
    translation('I_phys_psi' + str(index), 1079, 1137, y, index)

# Division II, numerical substructure.  The generated reference includes
# the left numerical vertical member joining all three beam levels.
for name, x, y1, y2 in [
    ('left_column',300,727,992),
    ('middle_column',451,727,1109),
    ('right_column',606,727,1118),
]:
    line('II_num_' + name, x, y1, x, y2)
for y in [727,861,992]:
    line('II_num_beam' + str(y),300,y,606,y)
base('II_num_node3_pinned',451,1109,True)
base('II_num_node4_fixed',606,1118,False)
for num, cx, cy in [
    (14,281,703),(15,433,703),(16,587,703),
    (10,273,834),(11,426,834),(12,581,834),
    (6,273,962),(7,422,962),(8,578,962),
    (3,422,1087),(4,577,1087),
]:
    node('II_num_node' + str(num), cx, cy, num)
for y, items in [
    (727, [(300,13),(451,14),(606,15)]),
    (861, [(300,8),(451,9),(606,10)]),
    (992, [(300,3),(451,4),(606,5)]),
]:
    for x, index in items:
        rotation('II_num_psi' + str(index), x, y, index,
                 retained=index in {4,9,14})
for y, index in [(727,11),(861,6),(992,1)]:
    translation('II_num_psi' + str(index), 619, 671, y, index)

# Division II, physical substructure (outer bay, all three storeys).
for x in [916,1064]:
    line('II_phys_column' + str(x), x,727,x,1117 if x == 916 else 1110)
for y in [727,861,992]:
    line('II_phys_beam' + str(y),916,y,1064,y)
base('II_phys_node1_fixed',916,1117,False)
base('II_phys_node2_pinned',1064,1110,True)
for num,cx,cy in [
    (13,893,704),(14,1044,703),(9,890,834),(10,1038,834),
    (5,887,961),(6,1037,962),(1,890,1089),(2,1040,1089),
]:
    node('II_phys_node' + str(num),cx,cy,num)
for y, items in [
    (727, [(916,12),(1064,13)]),
    (861, [(916,7),(1064,8)]),
    (992, [(916,2),(1064,3)]),
]:
    for x,index in items:
        rotation('II_phys_psi' + str(index),x,y,index)
for y,index in [(727,11),(861,6),(992,1)]:
    translation('II_phys_psi' + str(index),1079,1137,y,index,
                retained=index in {1,11})

s.text('retained_coordinate_legend',88,1180,1104,43,
       'Retained coordinates are highlighted in red; the other labelled coordinates are condensed.',
       size=25,color=RED,align='center')


def verify():
    expected = {
        'I_num': ({1,4,6,9,11,14}, {3,5,7,8,10,12,13,15}),
        'I_phys': ({1,6}, {2,3,7,8}),
        'II_num': ({1,4,6,9,11,14}, {3,5,8,10,13,15}),
        'II_phys': ({1,11}, {2,3,6,7,8,12,13}),
    }
    for prefix,(retained,condensed) in expected.items():
        coords = [o for o in s.objects
                  if o['name'].startswith('fig4_' + prefix + '_psi')
                  and o['name'].endswith('_label')]
        by_index = {int(o['text'][1:]):o for o in coords}
        assert len(by_index) == len(coords)
        assert set(by_index) == retained | condensed, (prefix,by_index)
        assert {i for i,o in by_index.items() if o['color']==RED} == retained
        assert {i for i,o in by_index.items() if o['color']==BLACK} == condensed
        for index in retained | condensed:
            colour = RED if index in retained else BLACK
            related = [o for o in s.objects
                       if o['name'].startswith('fig4_' + prefix + '_psi' + str(index) + '_')]
            assert all(o['color'] == colour for o in related)
    numbered_nodes = [o for o in s.objects
                      if '_node' in o['name']
                      and (o['name'].endswith('_circle') or o['name'].endswith('_number'))]
    assert len(numbered_nodes) == 76  # 38 nodes, 2 objects each.
    assert all(o['color'] == BLACK for o in numbered_nodes)
    assert len({o['name'] for o in s.objects}) == len(s.objects)
    assert all(o['kind'] != 'image' for o in s.objects)
    return {
        'objects':len(s.objects),'kinds':dict(Counter(o['kind'] for o in s.objects)),
        'labelled_dofs':sum(len(a | b) for a,b in expected.values()),
        'red_retained_dofs':sum(len(a) for a,b in expected.values()),
        'black_condensed_dofs':sum(len(b) for a,b in expected.values()),
        'black_node_labels':len(numbered_nodes)//2,
        'colour_check':'PASS','bitmap_objects':0,
    }


if __name__ == '__main__':
    result = verify()
    destination = Path(__file__).resolve().parent / 'fig4.json'
    s.save(destination)
    print(json.dumps(dict(output=str(destination),**result),ensure_ascii=False))
