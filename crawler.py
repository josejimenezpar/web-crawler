"""
crawler.py
==========
Punto de entrada del web crawler para muestras IRA.

Este archivo es un wrapper que importa la lógica principal de src/main.py.
"""

import sys
import os

sys.pycache_prefix = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "pycache")

from src.main import main

if __name__ == "__main__":
    main()

