"""SecondSelf: Root Oracle Q&A entry point (The Oracle - Task 4.1)."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.ask import main

if __name__ == "__main__":
    main()
