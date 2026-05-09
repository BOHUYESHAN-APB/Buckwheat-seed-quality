# Buckwheat YOLO Training Code

This directory contains the public training entry script used for the buckwheat seed quality model.

## Licensing scope

- The root repository keeps its original Apache-2.0 license for the pre-existing project content.
- The training workflow in this subdirectory is based on Ultralytics YOLO.
- The upstream `ultralytics` codebase used by this workflow is licensed under AGPL-3.0 / Enterprise terms.
- Any redistribution or reuse of this training workflow and related weights should follow the upstream Ultralytics license requirements.

## Included files

- `openi_train_buckwheat.py`: OpenI-oriented training entry for the buckwheat project.
- `UPSTREAM_LICENSE_AGPL-3.0.txt`: local copy of the upstream AGPL-3.0 license text from the training environment.

## Notes

- This public release only includes the training entry script intended for publication.
- Internal midterm materials, local review documents, 3D assets, monitoring code, and unpublished project materials are intentionally excluded.
- The script expects an Ultralytics source tree in the runtime environment; this directory does not bundle the full upstream source code.
