"""Shared constants and paths for the nearby-star pipeline."""
import os

import numpy as np

# Reference epochs for the two catalogues.
EPOCH_HIP  = 1991.25
EPOCH_GAIA = 2016.0

# Search volume. parallax[mas] = 1000 / distance[pc], so the parallax floor is
# 1000 / MAX_DIST_PC (a star at MAX_DIST_PC has exactly that parallax; nearer
# stars have larger parallaxes and pass the cut).
MAX_DIST_PC = 60.0
MIN_PARALLAX_MAS = 1000.0 / MAX_DIST_PC     # 60 pc -> 16.67 mas
MATCH_RADIUS_ARCSEC = 2.0

# Solar peculiar motion (Schonrich, Binney & Dehnen 2010) for optional LSR shift.
SOLAR_UVW = np.array([11.1, 12.24, 7.25])   # km/s

# Well-known nearby stars to label on the figures. Matched case-insensitively as
# substrings of proper_name, so "Procyon" also catches "Procyon A".
FAMOUS_STARS = [
    "Sirius", "Procyon", "Proxima Centauri", "Rigil Kentaurus", "Toliman",
    "Barnard", "Vega", "Altair", "Fomalhaut", "Aldebaran", "Arcturus",
    "Capella", "Pollux", "Castor", "Kapteyn", "Teegarden",
]

# Project root (parent of this package) — where output CSVs and PNGs land, so
# results are predictable regardless of the current working directory.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
