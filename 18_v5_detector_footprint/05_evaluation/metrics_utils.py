"""Integer support, explicit undefined ratios, no success from missing evidence."""
import math

def rate(numerator,denominator):
 if not isinstance(numerator,int) or isinstance(numerator,bool) or not isinstance(denominator,int) or isinstance(denominator,bool) or numerator<0 or denominator<0 or numerator>denominator:raise ValueError('invalid integer support')
 if denominator==0:return {'numerator':numerator,'denominator':denominator,'ratio':None,'wilson95':None}
 z=1.959963984540054;n=denominator;p=numerator/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
 return {'numerator':numerator,'denominator':n,'ratio':p,'wilson95':[max(0,c-h),min(1,c+h)]}

def require_coverage_gate(metrics,thresholds):
 """Require all prespecified confirmed rates, not raw mask or geometric success."""
 failed=[]
 for key,threshold in thresholds.items():
  item=metrics.get(key);r=item.get('ratio') if isinstance(item,dict) else None
  if r is None or not isinstance(r,(int,float)) or not math.isfinite(r) or r<threshold:failed.append(key)
 return {'passed':not failed,'failed_subgroups':failed,'basis':'AI_PROVISIONAL_REFERENCE_VISUALLY_CONFIRMED_COVERAGE'}
