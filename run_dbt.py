"""Run dbt with credentials from .env (works the same on Windows, macOS and Linux).

    python run_dbt.py build
    python run_dbt.py source freshness
    python run_dbt.py docs generate
"""

import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
dbt_dir = Path(__file__).parent / "dbt"
sys.exit(subprocess.call(["dbt", *sys.argv[1:], "--profiles-dir", "."], cwd=dbt_dir))
