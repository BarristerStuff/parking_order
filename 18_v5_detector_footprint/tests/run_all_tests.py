"""Run from system python3; use existing numeric runtime only where necessary.
No package installation. Bytecode compilation outputs confined to tests/bytecode.
"""
from pathlib import Path
import subprocess,json,sys,os,py_compile,hashlib,time
R=Path(__file__).resolve().parents[1]
NUMERIC='/home/yanbo/net_vlm_garbage_optimization/P3_detector_vlm/.venv_yoloe/bin/python'
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(R/'tests/runtime'),'YOLO_AUTOINSTALL':'false'}
(R/'tests/runtime').mkdir(exist_ok=True);(R/'tests/bytecode').mkdir(exist_ok=True)
compile_results=[]
for path in sorted(R.rglob('*.py')):
 if 'runtime' in path.parts:continue
 target=R/'tests/bytecode'/(hashlib.sha256(str(path).encode()).hexdigest()+'.pyc')
 try:py_compile.compile(str(path),cfile=str(target),doraise=True);compile_results.append({'file':str(path.relative_to(R)),'ok':True})
 except py_compile.PyCompileError as ex:compile_results.append({'file':str(path.relative_to(R)),'ok':False,'error':str(ex)})
results=[]
for name in ['test_matching.py','test_footprint.py','test_contracts.py','test_synthetic_rules.py','test_metrics.py','test_integration_guards.py']:
 executable=NUMERIC if name=='test_synthetic_rules.py' else sys.executable
 run=subprocess.run([executable,'-B',str(R/'tests'/name)],text=True,capture_output=True,env=env)
 results.append({'file':name,'python':executable,'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
report={'executed_at_unix':time.time(),'compile':compile_results,'suites':results,'passed':all(x['ok'] for x in compile_results) and all(x['returncode']==0 for x in results)}
(R/'tests/test_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(not report['passed'])
