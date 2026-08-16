import sys

from .demo import main

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print("usage: python -m fermion_garden  (runs the offline demo; no arguments accepted)")
        raise SystemExit(0)
    main()

