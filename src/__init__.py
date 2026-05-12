import sys
import os

sys.pycache_prefix = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build")
