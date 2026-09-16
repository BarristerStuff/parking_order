# ParkScope Segmentation Feasibility P0 Protocol

This is a one-shot, CPU-only audit of the official ParkScope `yolov11/v11n/best.pt` checkpoint at upstream commit `fbcfac7be597dd263570bbcd0377096c8a43d146`. The frozen v2.3 70-image pilot is reused without resampling. No GT, group, or event label may influence inference, filtering, or matching. No Ollama/VLM endpoint is contacted.

Inference is exactly `YOLO(best.pt).predict(source=image_path, device="cpu", save=False, verbose=False)` with no explicit confidence, IoU, image size, class, augmentation, or NMS overrides. All returned instances are retained. Frozen v2.3 selected-vehicle boxes are matched only against runtime class-name `vehicle` candidates by highest bbox IoU, then confidence descending, bbox area descending, and instance index ascending. IoU is binding evidence only, not a feasibility score.

GO requires all: 70/70 successful inference, vehicle-mask usable >= 0.95, normal marked-bay geometry usable >= 0.80, p01 outside evidence usable >= 8/10, p03 separator usable >= 7/10, and catastrophic wrong-mask rate <= 0.10. No threshold sweep, retry with changed parameters, checkpoint change, training, full DEV, VAL, or HOLDOUT is authorized.
