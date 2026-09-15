import json,urllib.request,time,hashlib
class OllamaClient:
 def __init__(self,endpoint,model,ledger=None):self.endpoint=endpoint;self.model=model;self.ledger=ledger
 def preflight(self):
  req=urllib.request.Request(self.endpoint+'/api/tags')
  with urllib.request.urlopen(req,timeout=10) as r:z=json.loads(r.read())
  names=[x.get('name') for x in z.get('models',[])]
  if self.model not in names:raise RuntimeError('required model missing: '+self.model)
 def ask(self,prompt,b64,token,rank):
  self.preflight();payload={'model':self.model,'prompt':prompt,'images':[b64],'stream':False,'format':{'type':'object','properties':{'answer':{'type':'string','enum':['A','B','C','D']}},'required':['answer'],'additionalProperties':False},'options':{'temperature':0,'num_predict':32},'think':False}
  if self.ledger:
   with open(self.ledger,'a') as f:f.write(json.dumps({'event':'request_start','sample_token':token,'vehicle_rank':rank,'timestamp':time.time()})+'\n');f.flush()
  t=time.perf_counter();req=urllib.request.Request(self.endpoint+'/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=240) as r:z=json.loads(r.read())
  a=json.loads(z['response'])['answer'];lat=time.perf_counter()-t
  if self.ledger:
   with open(self.ledger,'a') as f:f.write(json.dumps({'event':'request_result','sample_token':token,'vehicle_rank':rank,'timestamp':time.time(),'answer':a,'latency_seconds':lat})+'\n');f.flush()
  return a,lat
