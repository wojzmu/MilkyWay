"""Entry point for the nearby-star pipeline.

The implementation now lives in the milkyway/ package (see milkyway/__init__.py);
this file stays as the CLI entry point so `python MilkyWay.py [--plot-only]
[--csv FILE] [--min-mass MSUN]` keeps working, and re-exports the public API so
`from MilkyWay import <name>` still resolves.
"""
from milkyway import *          # noqa: F401,F403  (public API re-export)
from milkyway import main

# A few internal symbols kept importable for convenience / existing callers.
from milkyway.mass import _MASS_MG, _MASS_MSUN            # noqa: F401
from milkyway.classify import (_MS_BPRP, _MS_ABSG,        # noqa: F401
                               SPURIOUS_BELOW_MS_MAG, SPURIOUS_FAINT_G,
                               SPURIOUS_NOCOLOUR_MG)

if __name__ == "__main__":
    main()
