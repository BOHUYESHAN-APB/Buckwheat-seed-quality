#!/usr/bin/env python3
"""Wrapper: delegates to huawei_npu_migration/scripts/openi_prepare_dataset.py."""

import os
import sys


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    module = __import__(
        "huawei_npu_migration.scripts.openi_prepare_dataset",
        fromlist=["main"],
    )
    module.main()


if __name__ == "__main__":
    main()
