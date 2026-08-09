"""Script tuong thich nguoc cho phep chay: python tests/test_pipeline.py qua pytest."""
from __future__ import annotations

import sys
import pytest

if __name__ == "__main__":
    sys.exit(pytest.main(sys.argv[1:] or ["tests"]))
