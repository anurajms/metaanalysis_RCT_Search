"""
Entry point for running RCT Finder as a module.

Usage:
    python -m rct_finder --days 30 --output results.xlsx
"""

import sys

from .cli import parse_args, get_config_from_args
from .main import run_finder


def main():
    """Main entry point."""
    args = parse_args()
    config = get_config_from_args(args)
    
    try:
        records, excel_path, csv_path = run_finder(config)
        print(f"\n✓ Found {len(records)} unique RCT records")
        return 0
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        if config.get('verbose'):
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
