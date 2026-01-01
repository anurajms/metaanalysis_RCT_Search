"""
Simple script to run RCT Finder directly from an IDE.
Just click "Run" or press the run button in your IDE.

SETUP: Set your API keys as environment variables before running:
    export NCBI_API_KEY="your_ncbi_key_here"
    export SEMANTIC_SCHOLAR_API_KEY="your_semantic_scholar_key_here"

Or add them to your shell profile (~/.zshrc or ~/.bashrc) for persistence.
"""

import sys
import os

# Add parent directory to path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaanalysis_RCT_Search.config import DEFAULT_DAYS, DEFAULT_OUTPUT, get_default_api_keys
from metaanalysis_RCT_Search.main import run_finder


# ============================================================
# CONFIGURATION - Modify these settings as needed
# ============================================================

CONFIG = {
    # How many days to look back for RCTs
    'days': 30,
    
    # Output file path (Excel file, CSV will be created alongside)
    'output': 'rct_results.xlsx',
    
    # Maximum records per source (None = no limit)
    'max_records_per_source': 100,  # Set to None for no limit
    
    # Include preprints in results?
    'include_preprints': False,
    
    # Additional search query (optional)
    'query': None,  # e.g., "cardiology OR cardiac"
    
    # Specific sources to query (None = all available)
    # Options: 'pubmed', 'semanticscholar', 'europepmc', 'crossref', 'openalex'
    'sources': None,
    
    # Enable web scraping fallback
    'scrape_fallback': True,
    
    # Verbose logging
    'verbose': True,
    
    # Use LLM for topic classification
    'use_llm_classifier': False,
    
    # API Keys (loaded from environment variables)
    'api_keys': get_default_api_keys(),
}


# ============================================================
# MAIN EXECUTION
# ============================================================

def check_api_keys():
    """Check if API keys are set and display status."""
    keys = CONFIG['api_keys']
    print("\n--- API Key Status ---")
    
    ncbi_key = keys.get('ncbi')
    ss_key = keys.get('semantic_scholar')
    
    if ncbi_key:
        print(f"  ✓ NCBI_API_KEY: Set ({ncbi_key[:8]}...)")
    else:
        print("  ✗ NCBI_API_KEY: Not set (PubMed rate limit: 3 req/sec)")
        
    if ss_key:
        print(f"  ✓ SEMANTIC_SCHOLAR_API_KEY: Set ({ss_key[:8]}...)")
    else:
        print("  ✗ SEMANTIC_SCHOLAR_API_KEY: Not set")
    
    # Optional keys
    for key_name in ['scopus', 'wos', 'dimensions']:
        if keys.get(key_name):
            print(f"  ✓ {key_name.upper()}_API_KEY: Set")
    
    print()


if __name__ == '__main__':
    print("=" * 60)
    print("RCT FINDER - Starting...")
    print("=" * 60)
    
    check_api_keys()
    
    print("Settings:")
    print(f"  Days to search: {CONFIG['days']}")
    print(f"  Output file: {CONFIG['output']}")
    print(f"  Max records per source: {CONFIG['max_records_per_source'] or 'No limit'}")
    print(f"  Include preprints: {CONFIG['include_preprints']}")
    print(f"  Sources: {CONFIG['sources'] or 'All available'}")
    print()
    
    try:
        records, excel_path, csv_path = run_finder(CONFIG)
        print(f"\n✓ Found {len(records)} unique RCT records")
        print(f"\nResults saved to:")
        print(f"  Excel: {excel_path}")
        print(f"  CSV: {csv_path}")
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
