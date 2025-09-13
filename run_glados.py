#!/usr/bin/env python3
"""
Script de lancement principal pour GLaDOS
"""

import sys
from pathlib import Path

# Ajouter le répertoire du projet au path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from glados.main import cli_main

if __name__ == "__main__":
    sys.exit(cli_main())