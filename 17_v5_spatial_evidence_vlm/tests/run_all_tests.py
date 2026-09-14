import pathlib,subprocess,sys,json,os
R=pathlib.Path(__file__).resolve().parents[1];env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'};results=[]
for p in [R/'03_rule_engine/test_space_rule.py',R/'tests/test_contracts.py']:
 run=subprocess.run([sys.executable,str(p)],env=env,text=True,capture_output=True);results.append({'file':str(p),'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
(R/'tests/test_results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2));raise SystemExit(any(x['returncode'] for x in results))
