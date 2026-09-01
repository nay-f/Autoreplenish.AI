#!/usr/bin/env python3
"""Convenience alias to run scripts/02_seed_demo.py"""

import os
import sys

scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    from scripts.02_seed_demo import main
    main()
