def vehicle_decision(q1, q3=None, legacy=False):
    """Apply frozen v2.2 Q1/Q3 semantics at vehicle level."""
    if q1 == "A":
        return "in_bay"
    if q1 == "D":
        return "uncertain"
    if q1 in ("B", "C"):
        if q3 == "A":
            return "gate_queue"
        if q3 in ("B", "C"):
            return "outside_or_multibay"
        return "uncertain"
    return "uncertain"

def frame_decision(decisions):
    if not decisions:
        return "uncertain"
    if any(x == "outside_or_multibay" for x in decisions):
        return "positive"
    if any(x == "uncertain" for x in decisions):
        return "uncertain"
    return "negative"

def apply(vehicles, legacy=False):
    decisions = []
    for vehicle in vehicles:
        decision = vehicle_decision(vehicle.get("q1"), vehicle.get("q3"), legacy)
        vehicle["decision"] = decision
        decisions.append(decision)
    return frame_decision(decisions), [v for v in vehicles if v["decision"] == "gate_queue"]
