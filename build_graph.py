"""SecondSelf: Root graph builder entry point (The Cartographer - Task 3.1)."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.build_graph import main

if __name__ == "__main__":
    main()
