"""Execute existing suites with writes constrained to audit dir at Python audit-hook level.
Not OS isolation. No run_all_tests invocation (it writes outside C scope).
"""
import json,os,pathlib,subprocess,sys,time
sys.dont_write_bytecode=True
O=pathlib.Path(__file__).resolve().parent;R=O.parent
wrapper=r'''
import sys,os,pathlib,runpy
sys.dont_write_bytecode=True
root=pathlib.Path(sys.argv[1]).resolve(); script=pathlib.Path(sys.argv[2]).resolve()
def hook(event,args):
 if event=='open':
  path,mode,flags=args
  if isinstance(path,(str,bytes,os.PathLike)) and ((isinstance(mode,str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
   if not pathlib.Path(os.fsdecode(path)).resolve().is_relative_to(root):raise PermissionError('C_WRITE_SCOPE:'+str(path))
 if event in ('socket.connect','socket.bind','subprocess.Popen','os.system'):raise PermissionError('C_NO_NETWORK_OR_CHILD_PROCESS:'+event)
 if event in ('os.mkdir','os.remove','os.rmdir','os.rename','os.symlink','os.link'):
  raise PermissionError('C_TEST_NO_MUTATION:'+event)
sys.addaudithook(hook)
sys.path.insert(0,str(script.parent));sys.argv=[str(script)];runpy.run_path(str(script),run_name='__main__')
'''
report=[]
for name in ['test_matching.py','test_footprint.py','test_contracts.py','test_synthetic_rules.py']:
 executable='/home/yanbo/net_vlm_garbage_optimization/P3_detector_vlm/.venv_yoloe/bin/python' if name=='test_synthetic_rules.py' else sys.executable
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(O),XDG_CACHE_HOME=str(O),MPLCONFIGDIR=str(O))
 p=subprocess.run([executable,'-B','-c',wrapper,str(O),str(R/'tests'/name)],text=True,capture_output=True,env=env)
 report.append({'suite':name,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'python':executable})
result={'executed_at_unix':time.time(),'passed':all(x['returncode']==0 for x in report),'suites':report,'guard':'Python audit hook, not OS sandbox; no raw image or model execution intended'}
(O/'independent_test_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));sys.exit(not result['passed'])
