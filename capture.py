"""SecondSelf: Root capture entry point (The Archivist)."""

import sys
from pathlib import Path

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.capture import main

if __name__ == "__main__":
    main()
