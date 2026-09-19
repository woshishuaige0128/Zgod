"""Consolidate independent explicit-dash geometry and actual EMF record audit.

This is new evidence for the explicit-stroke implementation. It does not use
the earlier filled-outline patch's verification to establish correctness.
"""
from pathlib import Path
from lxml import etree as ET
import bisect, collections, hashlib, json, math, re, struct
import numpy as np

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[3]
OLD=HERE.parents[2]/'figure_all_ppt_20260907'
AUDIT=HERE/'audit'
TRACE=HERE/'segment_trace';TRACE.mkdir(exist_ok=True)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def parse_points(text):return np.array([[float(v) for v in row.split(',')[:2]] for row in text.split(';')])
def emf_records(data):
    offset=0
    while offset<len(data):
        kind,size=struct.unpack_from('<II',data,offset)
        assert size>=8 and size%4==0 and offset+size<=len(data)
        yield kind,data[offset:offset+size]
        offset+=size
    assert offset==len(data)

def verify_native_paints(recs):
    objects={};selected={'pen':('stock',7),'brush':('stock',0)};stack=[]
    for kind,body in recs:
        if kind==33:stack.append(selected.copy())
        elif kind==34:selected=stack.pop()
        elif kind in (39,95):
            handle=struct.unpack_from('<I',body,8)[0]
            objects[handle]='brush' if kind==39 else 'pen'
        elif kind==37:
            handle=struct.unpack_from('<I',body,8)[0]
            if handle&0x80000000:
                stock=handle&0x7fffffff
                if stock<=5 or stock==18:selected['brush']=('stock',stock)
                elif stock in (6,7,8,19):selected['pen']=('stock',stock)
            else:selected[objects[handle]]=('handle',handle)
        elif kind==40:objects.pop(struct.unpack_from('<I',body,8)[0],None)
        elif kind==90:
            assert selected['brush']==('stock',5),'Native dash/line must use NULL_BRUSH'
            assert selected['pen'][0]=='handle'
        elif kind==91:
            # Figure15 has two pre-existing genuine filled multi-polygons.
            # They use NULL_PEN and must remain; they are not dash outlines.
            assert selected['pen']==('stock',8),'Filled polygon must use NULL_PEN'
    assert not stack

geometry=json.loads((AUDIT/'explicit_geometry_verification.json').read_text())
assert geometry['pass_check'] and geometry['checked_dash_draws']==98 and geometry['subpaths']==16691
for path,digest in geometry['hashes'].items():
    assert sha(PROJECT/path)==digest
assert sha(HERE/'VectorRecorder.cs')==sha(OLD/'VectorRecorder.cs')
rows=[];all_source_sha={};all_output_sha={};max_endpoint=0.;total_non_dashed=0
for n in range(5,16):
    source=OLD/'vectors'/f'fig{n}_gdi.xml';target=HERE/'vectors'/f'fig{n}_explicit.xml'
    old=ET.parse(source).getroot();new=ET.parse(target).getroot()
    assert old.attrib==new.attrib and len(old)==len(new)
    details=[];non_dashed=0;end_error=0.;subpaths=0
    for index,(a,b) in enumerate(zip(old,new)):
        if not a.get('stroke-dasharray'):
            assert ET.tostring(a)==ET.tostring(b)
            non_dashed+=1;continue
        assert {k:v for k,v in a.attrib.items() if k not in ('stroke-dasharray','stroke-dashoffset')}==b.attrib
        assert [ET.tostring(x) for x in a.findall('clip')]==[ET.tostring(x) for x in b.findall('clip')]
        points=parse_points(a.findtext('path'));lens=np.linalg.norm(np.diff(points,axis=0),axis=1)
        cumulative=np.r_[0,np.cumsum(lens)];total=float(cumulative[-1])
        pattern=np.array([float(x) for x in re.split(r'[,\s]+',a.get('stroke-dasharray'))])
        prefix=np.r_[0,np.cumsum(pattern)];cycle=float(pattern.sum())
        intervals=[]
        for k in range(math.ceil(total/cycle)):
            for j in range(0,len(pattern),2):
                s0=float(k*cycle+prefix[j]);s1=min(float(k*cycle+prefix[j+1]),total)
                if s0<total:intervals.append((s0,s1))
        actual=[parse_points(part) for part in b.findtext('path').split('|')]
        assert len(actual)==len(intervals)
        segments=[]
        for (s0,s1),p in zip(intervals,actual):
            j0=min(np.searchsorted(cumulative,s0,side='right')-1,len(lens)-1)
            j1=min(np.searchsorted(cumulative,s1,side='left')-1,len(lens)-1)
            q0=points[j0]+(points[j0+1]-points[j0])*(s0-cumulative[j0])/lens[j0]
            q1=points[j1]+(points[j1+1]-points[j1])*(s1-cumulative[j1])/lens[j1]
            expected=np.vstack([q0,points[j0+1:j1+1],q1])
            assert len(p)==len(expected)
            error=float(np.max(np.abs(p-expected)));assert error<1e-7
            endpoint_error=float(max(np.max(np.abs(p[0]-q0)),np.max(np.abs(p[-1]-q1))))
            end_error=max(end_error,endpoint_error)
            segments.append(dict(source_arclength_interval=[s0,s1],source_edge_indices=[int(j0),int(j1)],
                                 expected_start=q0.tolist(),expected_end=q1.tolist(),
                                 actual_start=p[0].tolist(),actual_end=p[-1].tolist(),
                                 retained_interior_vertices=len(p)-2,max_coordinate_error_pt=error))
        details.append(dict(source_draw_index=index,source_parameters=dict(a.attrib),
                            total_source_arclength_pt=total,source_point_count=len(points),
                            original_path_sha256=hashlib.sha256(a.findtext('path').encode()).hexdigest(),
                            explicit_path_sha256=hashlib.sha256(b.findtext('path').encode()).hexdigest(),
                            source_clip_sha256=[hashlib.sha256(ET.tostring(x)).hexdigest() for x in a.findall('clip')],
                            visible_segment_count=len(segments),segments=segments))
        subpaths+=len(actual)
    trace_path=TRACE/f'fig{n}.json'
    trace_path.write_text(json.dumps(dict(figure=n,dash_elements=details),separators=(',',':')),encoding='utf-8')
    emf=HERE/'vectors'/f'fig{n}_explicit.emf';data=emf.read_bytes();recs=list(emf_records(data));count=collections.Counter(t for t,_ in recs)
    source_emf=OLD/'vectors'/f'fig{n}_gdi.emf';old_emf=source_emf.read_bytes()
    old_count=collections.Counter(t for t,_ in emf_records(old_emf))
    assert recs[0][0]==1 and recs[-1][0]==14
    assert struct.unpack_from('<I',data,48)[0]==len(data)
    assert struct.unpack_from('<I',data,52)[0]==len(recs)
    bitmap={76,77,78,79,80,81,93,94,114,116};assert not(set(count)&bitmap)
    assert count[63]==0
    verify_native_paints(recs)
    assert data[24:40]==old_emf[24:40],'EMF physical frame must remain unchanged'
    added_native_dash_records=count[90]-old_count[90]
    assert added_native_dash_records==len(details),(n,added_native_dash_records,len(details))
    rows.append(dict(figure=n,dash_elements=len(details),visible_segments=subpaths,
                     non_target_draws_unchanged=True,non_target_draw_count=non_dashed,
                     clip_and_other_stroke_attributes_unchanged=True,
                     max_endpoint_error_source_pt=end_error,no_bitmap_records=True,
                     native_dash_polyline_records=added_native_dash_records,compound_dash_fill_records=0,
                     preexisting_native_polyline_records=old_count[90],
                     genuine_null_pen_filled_polygons=count[91],
                     source_xml_sha256=sha(source),explicit_xml_sha256=sha(target),
                     emf_path=str(emf),emf_sha256=sha(emf),
                     segment_trace_path=str(trace_path),segment_trace_sha256=sha(trace_path)))
    all_source_sha[str(source)]=sha(source);all_output_sha[str(emf)]=sha(emf)
    max_endpoint=max(max_endpoint,end_error);total_non_dashed+=non_dashed
fig5_identical=(HERE/'vectors/fig5_explicit.emf').read_bytes()==(OLD/'vectors/fig5_gdi.emf').read_bytes()
assert fig5_identical
report=dict(passed=True,figures=list(range(5,16)),changed_figures=list(range(6,16)),
            dash_elements=sum(r['dash_elements'] for r in rows),
            visible_segments=sum(r['visible_segments'] for r in rows),
            max_endpoint_error_source_pt=max_endpoint,
            max_coordinate_error_source_pt=geometry['max_coordinate_error_pt'],
            max_interval_arclength_error_source_pt=geometry['max_interval_arclength_error_pt'],
            geometry_tolerance_source_pt=1e-7,
            non_target_draws_unchanged=True,non_target_draw_count=total_non_dashed,
            non_target_preservation_scope='Original XML draw instructions, their geometry, attributes and clip paths; independently compared before unchanged GDI recorder execution',
            clips_and_non_dash_stroke_parameters_unchanged=True,
            no_bitmap_records=True,fig5_byte_identical=fig5_identical,
            original_gdi_recorder_code_sha256=sha(OLD/'VectorRecorder.cs'),
            explicit_gdi_recorder_code_byte_identical=True,
            independent_geometry_audit_path=str(AUDIT/'explicit_geometry_verification.json'),
            independent_geometry_audit_sha256=sha(AUDIT/'explicit_geometry_verification.json'),
            source_xml_sha256=all_source_sha,output_emf_sha256=all_output_sha,records=rows)
assert report['dash_elements']==98 and report['visible_segments']==16691
(HERE/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('records','source_xml_sha256','output_emf_sha256')},indent=2))
