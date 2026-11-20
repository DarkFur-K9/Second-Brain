"""SecondSelf: Root linking entry point (The Librarian - Task 2.2)."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.link import main

if __name__ == "__main__":
    main()
