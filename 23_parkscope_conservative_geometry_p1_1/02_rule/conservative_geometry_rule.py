#!/usr/bin/env python3
"""Frozen ParkScope P1.1 conservative geometry triage rule (geometry-only)."""
from __future__ import annotations
import itertools

def as_bool(value):
    return str(value).lower() == "true"

def angle_diff(a, b):
    d = abs(float(a) - float(b)) % 180.0
    return min(d, 180.0 - d)

def derive_evidence(components, config):
    lines = [c for c in components if float(c['elongation']) >= config['line_elongation_min'] and float(c['thickness_ratio']) <= config['line_max_thickness_ratio']]
    areas = [c for c in components if c not in lines]
    separator_components = [c for c in lines if as_bool(c['line_crosses_central_ground_span']) and float(c['distance_to_bottom_center_normalized']) <= config['separator_center_margin']]
    strong_separator = bool(separator_components)
    bracket_pairs = []
    for a, b in itertools.combinations(lines, 2):
        if angle_diff(a['orientation_deg'], b['orientation_deg']) > config['parallel_angle_max']:
            continue
        sa, sb = float(a['signed_normal_offset']), float(b['signed_normal_offset'])
        if sa * sb >= 0:
            continue
        gap = abs(sa - sb)
        if gap <= config['bracket_max_distance_ratio']:
            bracket_pairs.append((a, b, gap))
    best_area_support = max([max(float(c['overlap_with_ground_proxy']), 1.0 if as_bool(c['bottom_center_inside_area']) else 0.0) for c in areas] or [0.0])
    strong_bracket = bool(bracket_pairs)
    strong_area = best_area_support >= config['area_support_min']
    return {
        'strong_separator': strong_separator,
        'strong_bracket': strong_bracket,
        'strong_area': strong_area,
        'strong_in_bay': strong_bracket or strong_area,
        'line_count': len(lines),
        'area_count': len(areas),
        'separator_component_indices': [c['instance_index'] for c in separator_components],
        'bracket_pair_count': len(bracket_pairs),
        'best_bracket_gap': min([x[2] for x in bracket_pairs] or [None], key=lambda x: float('inf') if x is None else x),
        'best_area_support': best_area_support,
        'geometry_candidate_count': len(components),
    }

def decide_target(anchor_status, components, config):
    if anchor_status != 'ANCHOR_VALID':
        return 'UNCERTAIN_ANCHOR', {'strong_separator': False, 'strong_in_bay': False, 'geometry_candidate_count': len(components)}
    evidence = derive_evidence(components, config)
    if evidence['strong_separator'] and evidence['strong_in_bay']:
        return 'UNCERTAIN_CONFLICT', evidence
    if evidence['strong_separator']:
        return 'POSITIVE_MULTIBAY', evidence
    if evidence['strong_in_bay']:
        return 'NEGATIVE_IN_BAY', evidence
    return 'UNCERTAIN_NO_EVIDENCE', evidence

def fuse_frame(target_decisions):
    if any(x == 'POSITIVE_MULTIBAY' for x in target_decisions):
        return 'positive'
    if target_decisions and all(x == 'NEGATIVE_IN_BAY' for x in target_decisions):
        return 'negative'
    return 'uncertain'
