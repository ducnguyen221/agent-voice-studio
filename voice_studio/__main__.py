"""`python -m voice_studio <lệnh> …` — tương đương lệnh `voice-studio`."""
import sys

from .cli import main

sys.exit(main())
