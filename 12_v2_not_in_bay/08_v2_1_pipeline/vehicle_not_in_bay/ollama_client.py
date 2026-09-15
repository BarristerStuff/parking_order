"""Thread-safe Ollama JSON client with bounded retry and auditable ledger."""
import json,time,threading,urllib.request
class OllamaClient:
 def __init__(self,endpoint,model,ledger=None,config=None):
  self.endpoint=endpoint.rstrip('/');self.model=model;self.ledger=ledger;self.config=config or {};self.lock=threading.Lock();self._healthy=False;self.preflight()
 def preflight(self):
  with urllib.request.urlopen(self.endpoint+'/api/tags',timeout=10) as r:z=json.load(r)
  if self.model not in [m.get('name') for m in z.get('models',[])]:raise RuntimeError('required model missing: '+self.model)
  self._healthy=True
 def _log(self,obj):
  if self.ledger:
   with self.lock:
    with open(self.ledger,'a',encoding='utf-8') as f:f.write(json.dumps(obj,ensure_ascii=False)+'\n');f.flush()
 def ask(self,prompt,b64,token,rank,question='q1'):
  retries=int(self.config.get('max_retries',2));timeout=float(self.config.get('timeout_seconds',240));last=None
  for attempt in range(1,retries+2):
   if not self._healthy:self.preflight()
   self._log({'event':'request_start','sample_token':token,'vehicle_rank':rank,'question':question,'attempt':attempt,'timestamp':time.time()})
   payload={'model':self.model,'prompt':prompt,'images':[b64],'stream':False,'format':{'type':'object','properties':{'answer':{'type':'string','enum':['A','B','C','D']}},'required':['answer'],'additionalProperties':False},'options':{'temperature':0,'num_predict':int(self.config.get('num_predict',32))},'think':False};started=time.perf_counter()
   try:
    req=urllib.request.Request(self.endpoint+'/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:z=json.load(r)
    ans=json.loads(z['response'])['answer']
    if ans not in 'ABCD':raise ValueError('schema answer')
    latency=time.perf_counter()-started;self._log({'event':'request_result','sample_token':token,'vehicle_rank':rank,'question':question,'attempt':attempt,'timestamp':time.time(),'answer':ans,'latency_seconds':latency,'schema_success':True});return ans,latency
   except Exception as exc:
    last=exc;self._healthy=False;self._log({'event':'request_result','sample_token':token,'vehicle_rank':rank,'question':question,'attempt':attempt,'timestamp':time.time(),'error':str(exc),'schema_success':False})
    if attempt>retries:raise
  raise last
