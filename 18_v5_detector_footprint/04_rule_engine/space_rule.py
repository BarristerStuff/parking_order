"""Synthetic-only spatial-rule regression adapter, not an authorized pilot classifier.
The reviewed V5 image-raster implementation is snapshotted locally. All calls are
restricted to analytic fixtures; real image targets fail closed before geometry.
"""
import json
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location('v5_frozen_rule_core',ROOT/'synthetic_core.py')
core=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(core)

def build_spatial_evidence(vehicle,roi_config):
 if not roi_config or roi_config.get('scope')!='SYNTHETIC_UNIT_TEST_ONLY' or not str(vehicle.get('image_id','')).startswith('SYNTH_'):
  return {'image_id':vehicle.get('image_id'),'vehicle_id':vehicle.get('vehicle_id'),'scope':'BLOCKED_NO_TRUSTED_GEOMETRY','evidence_status':'uncertain','evidence_reason':'FORMAL_PILOT_CLASSIFICATION_NOT_AUTHORIZED','road_overlap_ratio':None}
 evidence=core.build_spatial_evidence(vehicle,roi_config)
 evidence['scope']='SYNTHETIC_UNIT_TEST_ONLY'
 return evidence

def decide_from_spatial_evidence(evidence,context):
 if evidence.get('scope')!='SYNTHETIC_UNIT_TEST_ONLY':
  return {'image_id':evidence.get('image_id'),'vehicle_id':evidence.get('vehicle_id'),'label':'uncertain','alert':False,'reason_code':'FORMAL_PILOT_CLASSIFICATION_NOT_AUTHORIZED','scope':'BLOCKED'}
 decision=core.decide_from_spatial_evidence(evidence,context)
 return {**decision,'scope':'SYNTHETIC_UNIT_TEST_ONLY'}

def aggregate_image_decision(decisions,*,detector_complete=False):
 return core.aggregate_image_decision(decisions,detector_complete=detector_complete)
