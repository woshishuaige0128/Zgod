"""Editable native-object reconstruction of the generated Figure 1 reference.

The source image supplies only the geometry and style reference.  No image or
SVG object is stored in this scene.  Scientific corrections are specified by
the active figure audit: S_a transpose in force placement and + on the top
summation input because the negative LQR law is already inside its block.
"""
from pathlib import Path
from collections import Counter
from scene import Scene, BLACK, BLUE, RED


def run(text, italic=False, bold=False, baseline=0, scale=1):
    r = {"text": text}
    if italic:
        r["italic"] = True
    if bold:
        r["bold"] = True
    if baseline:
        r["baseline"] = baseline
    if scale != 1:
        r["scale"] = scale
    return r


def sub(text):
    return run(text, italic=True, baseline=-25, scale=.72)


def sup(text):
    return run(text, italic=True, baseline=35, scale=.72)


s = Scene(1, 1672, 941)

# Pale native fills replace only the incidental texture in the reference.
s.rect('channel_force_block', 301, 120, 503, 151,
       fill='#FDE8E8', color=RED, width=4, radius=14)
s.rect('lqr_block', 903, 120, 470, 151,
       fill='#E9F5FF', color=BLUE, width=4, radius=14)
s.rect('cr_update_block', 563, 392, 579, 157,
       fill='#F7F6F7', color=BLACK, width=4, radius=14)
s.rect('channel_reaction_block', 301, 669, 501, 151,
       fill='#FDE8E8', color=RED, width=4, radius=14)
s.rect('physical_reaction_block', 875, 670, 507, 150,
       fill='#FBFAFB', color=BLACK, width=4, radius=14)

# Forward path and the two return branches, preserving the reference routing.
s.arrow('external_force_arrow', [[41, 471], [191, 471]], BLACK, 3.8, 23)
s.arrow('summation_to_cr', [[289, 471], [563, 471]], BLACK, 3.8, 23)
s.arrow('output_arrow', [[1142, 471], [1540, 471]], BLACK, 3.8, 23)
s.arrow('feedback_to_lqr', [[1445, 471], [1445, 196], [1373, 196]],
        BLUE, 4, 24)
s.arrow('lqr_to_force_channels', [[903, 196], [804, 196]], BLUE, 4, 24)
s.arrow('force_channels_to_sum', [[301, 196], [239, 196], [239, 422]],
        RED, 4, 25)
s.arrow('feedback_to_physical', [[1445, 471], [1445, 745], [1382, 745]],
        BLACK, 3.8, 24)
s.arrow('physical_to_reaction_channels', [[875, 745], [802, 745]],
        BLACK, 3.8, 24)
s.arrow('reaction_channels_to_sum', [[301, 745], [239, 745], [239, 519]],
        RED, 4, 25)

s.ellipse('summation_circle', 191, 423, 98, 95,
          fill='#FFFFFF', color=BLACK, width=3.8)
s.ellipse('feedback_junction', 1435, 461, 20, 20,
          fill=BLACK, color=BLACK, width=0)

# Every formula and its upper/lower indices belongs to one text object.
s.text('force_channel_title', 326, 147, 453, 61,
       'Channel delays H_a(z)', 44, align='center', runs=[
           run('Channel delays '), run('H', italic=True, bold=True), sub('a'),
           run('(z)', italic=True)])
s.text('force_channel_placement', 326, 203, 453, 58,
       'Force placement S_a^T', 44, align='center', runs=[
           run('Force placement '), run('S', italic=True), sub('a'), sup('T')])

s.text('lqr_title', 928, 148, 420, 59, 'LQR force', 44, align='center')
s.text('lqr_law', 922, 201, 432, 65,
       '−K_x S_a q−K_v S_a q\u0307', 44, align='center', runs=[
           run('−'), run('K', italic=True, bold=True), sub('x'), run(' '),
           run('S', italic=True, bold=True), sub('a'),
           run('q', italic=True, bold=True), run(' − '),
           run('K', italic=True, bold=True), sub('v'), run(' '),
           run('S', italic=True, bold=True), sub('a'),
           run('q\u0307', italic=True, bold=True)])

s.text('cr_title', 598, 420, 509, 60, 'CR update', 44, align='center')
s.text('cr_contents', 594, 477, 517, 61,
       'Numerical inertia, C_0, K_0', 43, align='center', runs=[
           run('Numerical inertia, '), run('C', italic=True, bold=True),
           sub('0'), run(', '), run('K', italic=True, bold=True), sub('0')])

s.text('reaction_channel_title', 326, 694, 451, 59,
       'Channel delays z^(−n_ℓ)', 43, align='center', runs=[
           run('Channel delays '), run('z', italic=True),
           sup('−n'), run('ℓ', italic=True, baseline=15, scale=.54)])
s.text('reaction_channel_sum', 326, 751, 451, 59,
       'Sum over ℓ', 44, align='center', runs=[
           run('Sum over '), run('ℓ', italic=True)])
s.text('physical_title', 895, 695, 467, 59,
       'Physical reaction terms', 44, align='center')
s.text('physical_law', 900, 751, 457, 62,
       'K_ℓ q+C_ℓ q\u0307', 44, align='center', runs=[
           run('K', italic=True, bold=True), sub('ℓ'),
           run('q', italic=True, bold=True), run(' + '),
           run('C', italic=True, bold=True), sub('ℓ'),
           run('q\u0307', italic=True, bold=True)])

s.text('external_force_label', 47, 400, 128, 62,
       'f_red', 49, runs=[run('f', italic=True),
                         run('red', baseline=-25, scale=.72)])
s.text('summation_sigma', 194, 429, 92, 85, 'Σ', 60, align='center')
s.text('summation_top_plus', 176, 375, 46, 53, '+', 48, align='center')
s.text('summation_bottom_minus', 176, 509, 46, 53, '−', 48, align='center')
s.text('state_output_label', 1553, 436, 114, 68,
       'q, q\u0307', 47, runs=[
           run('q', italic=True, bold=True), run(', '),
           run('q\u0307', italic=True, bold=True)])

target = Path(__file__).with_name('fig1.json')
names = [o['name'] for o in s.objects]
assert len(set(names)) == len(names), 'Object names must be unique'
assert all(o['kind'] in {'path', 'rect', 'ellipse', 'text'} for o in s.objects)
assert all(o.get('w', 1) > 0 and o.get('h', 1) > 0 for o in s.objects)
assert next(o for o in s.objects if o['name'].endswith('summation_top_plus'))['text'] == '+'
assert 'M' not in next(o for o in s.objects if o['name'].endswith('physical_law'))['text']
s.save(target)
print(target)
print(dict(Counter(o['kind'] for o in s.objects)))
print('total_objects', len(s.objects))
