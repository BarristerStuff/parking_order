"""Render only verified allowlist images; no label reads. Rendering is not review."""
import json, math
from pathlib import Path
from PIL import Image, ImageDraw
from footprint import ROOT, METHODS, verified_image, digest

def render(source, output_name='footprint_outputs.jsonl'):
    targets=[json.loads(s) for s in Path(source).read_text().splitlines()]
    rows=[json.loads(s) for s in (ROOT/output_name).read_text().splitlines()]
    bykey={}
    for r in rows: bykey.setdefault((r['image_id'],r['vehicle_id']),{})[r['method']]=r
    # Fixed evenly spaced 16 unique targets + up to eight first instances of distinct risk codes.
    selected=sorted(set(round(i*(len(targets)-1)/15) for i in range(16))) if targets else []
    riskseen=set();risks=[]
    for i,t in enumerate(targets):
        rr=bykey[(t['image_id'],t['vehicle_id'])][METHODS[0]]
        for reason in rr['reasons']:
            if reason not in ('contour_provenance_unknown','visible_bottom_band_is_only_proxy') and reason not in riskseen:
                riskseen.add(reason)
                if i not in selected and i not in risks and len(risks)<8: risks.append(i)
    selected+=risks
    dest=ROOT/'footprint_visuals';dest.mkdir(exist_ok=True)
    index=[];tiles=[]
    for number,i in enumerate(selected,1):
        t=targets[i]; pair=bykey[(t['image_id'],t['vehicle_id'])]; a,b=pair[METHODS[0]],pair[METHODS[1]]
        im=verified_image(t['image_id']);x1,y1,x2,y2=t['bbox_xyxy']
        pad=max(16,.15*max(x2-x1,y2-y1));bounds=(max(0,int(x1-pad)),max(0,int(y1-pad)),min(im.width,int(x2+pad+1)),min(im.height,int(y2+pad+1)))
        original=im.crop(bounds); overlay=original.copy();d=ImageDraw.Draw(overlay)
        def line(poly,color,width=2):
            if poly and all(math.isfinite(v) for pt in poly for v in pt):
                pts=[(x-bounds[0],y-bounds[1]) for x,y in poly]; d.line(pts+[pts[0]],fill=color,width=width)
        line(t.get('mask_polygon_image'),'cyan',2)
        line(a['contact_band_polygon'],'orange',4)
        line(b['bbox_proxy_polygon'],'magenta',2)
        tile=Image.new('RGB',(1000,350),'#202020');td=ImageDraw.Draw(tile)
        title=f"{number:02} {t['image_id']} {t['vehicle_id']} | A:{a['status']} B:{b['status']}"
        td.text((8,7),title,fill='white');td.text((8,26),'RAW LEFT | CYAN visible mask / ORANGE band / MAGENTA bbox proxy',fill='white')
        for j,pic in enumerate([original,overlay]):
            pic.thumbnail((490,270));tile.paste(pic,(j*500+(500-pic.width)//2,52+(270-pic.height)//2))
        td.text((8,332),','.join(a['reasons'])[:130],fill='yellow')
        tiles.append(tile)
        cropfile=None
        if i in risks:
            cropfile=dest/f'risk_{number:02}_{t["image_id"]}_{t["vehicle_id"]}.jpg'
            big=Image.new('RGB',(original.width*2,original.height+45),'#202020');big.paste(original,(0,45));big.paste(overlay,(original.width,45));ImageDraw.Draw(big).text((5,5),title,fill='white');big.save(cropfile)
        index.append({'number':number,'image_id':t['image_id'],'vehicle_id':t['vehicle_id'],'target_index':i,'sample_basis':'risk_first_occurrence' if i in risks else 'fixed_evenly_spaced',
                      'montage':str(dest/f'montage_{(number-1)//4+1:02}.jpg'),'risk_enlargement':str(cropfile) if cropfile else None,'source_sha256':digest(source),'review_status':'unreviewed'})
    for start in range(0,len(tiles),4):
        sheet=Image.new('RGB',(1000,350*len(tiles[start:start+4])),'#202020')
        for j,tile in enumerate(tiles[start:start+4]):sheet.paste(tile,(0,j*350))
        sheet.save(dest/f'montage_{start//4+1:02}.jpg',quality=92)
    (dest/'visual_index.json').write_text(json.dumps(index,indent=2)+'\n')
    return index
if __name__=='__main__':
    import sys
    print(json.dumps(render(sys.argv[1]),indent=2))
