"""Pytest configuration."""

import sys
from pathlib import Path

# Add repo root to path so tests can import as `generators.x`
sys.path.insert(0, str(Path(__file__).parent.parent))
