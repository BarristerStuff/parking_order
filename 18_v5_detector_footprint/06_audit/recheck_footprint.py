"""Replay reviewed pure methods on saved targets (no images). Independent bbox formula.
Never calls footprint.run, verified_image, or freeze_contract.
"""
import sys,os,pathlib,json,hashlib,importlib.util
sys.dont_write_bytecode=True
O=pathlib.Path(__file__).resolve().parent;B=O.parent/'02_footprint_audit'
def guard(event,args):
 if event=='open':
  path,mode,flags=args
  if isinstance(path,(str,bytes,os.PathLike)) and ((isinstance(mode,str) and any(x in mode for x in 'wax+')) or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
   if not pathlib.Path(os.fsdecode(path)).resolve().is_relative_to(O):raise PermissionError('C_WRITE_SCOPE')
 if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.mkdir','os.remove','os.rename'):raise PermissionError('C_NO_SIDE_EFFECT:'+event)
sys.addaudithook(guard)
spec=importlib.util.spec_from_file_location('footprint_pure_reviewed',B/'footprint.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
loadl=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
metrics=json.loads((B/'footprint_metrics.json').read_text());source=pathlib.Path(metrics['source'])
targets=loadl(source);actual=loadl(B/'footprint_outputs.jsonl');bykey={(x['image_id'],x['vehicle_id'],x['method']):x for x in actual};bad=[];analytic_bad=[]
for target in targets:
 for row in module.process_target(target,*target['source_size']):
  key=(row['image_id'],row['vehicle_id'],row['method']);stored=bykey.get(key)
  if stored is None or any(v!=stored.get(k) for k,v in row.items() if k!='visual_review'):bad.append(key)
 box=target['bbox_xyxy'];x1,y1,x2,y2=box;cut=y1+.8*(y2-y1);expected=[[x1,cut],[x2,cut],[x2,y2],[x1,y2]]
 row=bykey[(target['image_id'],target['vehicle_id'],'bbox_lower_conservative_proxy')]
 if row['bbox_proxy_polygon'] is None or any(abs(a-b)>1e-9 for pa,pb in zip(expected,row['bbox_proxy_polygon']) for a,b in zip(pa,pb)):analytic_bad.append(target['vehicle_id'])
result={'pure_replay_status':'PASS' if not bad and len(actual)==2*len(targets) else 'FAIL','pure_replay_rows':2*len(targets),'mismatches':bad,'independent_bbox_formula_status':'PASS' if not analytic_bad else 'FAIL','bbox_formula_mismatches':analytic_bad,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'code_sha256':hashlib.sha256((B/'footprint.py').read_bytes()).hexdigest(),'limitation':'Pure method replay tests reproducibility, not independent proof of mask geometry correctness. Independent analytic check is bbox lower 20% only. No pixels, models, network, or physical ground validation.'}
(O/'footprint_replay_result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));sys.exit(bool(bad or analytic_bad))
