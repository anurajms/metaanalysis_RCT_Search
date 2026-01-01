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
    'days': 60,
    
    # Output file path (Excel file, CSV will be created alongside)
    'output': 'rct_results.xlsx',
    
    # Maximum records per source (None = no limit)
    'max_records_per_source': None,  # Set to None for no limit
    
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
# HELPER FUNCTIONS
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


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    """Ask a yes/no question and return the answer."""
    suffix = " [y/N]: " if not default else " [Y/n]: "
    try:
        response = input(prompt + suffix).strip().lower()
        if not response:
            return default
        return response in ('y', 'yes')
    except (EOFError, KeyboardInterrupt):
        return default


def run_llm_refinement(records: list, output_path: str):
    """Run LLM-based classification refinement using LM Studio."""
    from metaanalysis_RCT_Search.llm_classifier import (
        check_lm_studio_connection,
        get_available_models,
        get_loaded_model,
        refine_classification_with_llm,
        save_llm_refined_results
    )
    
    print("\n" + "=" * 60)
    print("LLM CLASSIFICATION REFINEMENT")
    print("=" * 60)
    
    # Check LM Studio connection
    print("\nChecking LM Studio connection...")
    if not check_lm_studio_connection():
        print("  ✗ LM Studio is not running or not accessible at localhost:1234")
        print("  Please start LM Studio and load a model, then run again.")
        return None
    
    print("  ✓ LM Studio connected")
    
    # Get available models
    models = get_available_models()
    
    if not models:
        print("  ✗ No models found in LM Studio")
        print("  Please load a model in LM Studio first.")
        return None
    
    # Display available models
    print(f"\n--- Available Models ({len(models)}) ---")
    for idx, model in enumerate(models, 1):
        model_id = model.get('id', 'Unknown')
        # Try to extract a friendly name
        friendly_name = model_id.split('/')[-1] if '/' in model_id else model_id
        print(f"  [{idx}] {friendly_name}")
        if model_id != friendly_name:
            print(f"      Full ID: {model_id}")
    
    # Let user select model
    selected_model_id = None
    while selected_model_id is None:
        try:
            selection = input(f"\nSelect model (1-{len(models)}) or 'q' to cancel: ").strip().lower()
            
            if selection == 'q':
                print("LLM refinement cancelled.")
                return None
            
            idx = int(selection) - 1
            if 0 <= idx < len(models):
                selected_model_id = models[idx].get('id')
                print(f"  ✓ Selected: {selected_model_id}")
            else:
                print(f"  ✗ Please enter a number between 1 and {len(models)}")
        except ValueError:
            print(f"  ✗ Please enter a valid number or 'q' to cancel")
        except (EOFError, KeyboardInterrupt):
            print("\nLLM refinement cancelled.")
            return None
    
    # Confirm with user
    print(f"\nReady to refine classification for {len(records)} records.")
    print("This may take a few minutes depending on your model speed.")
    
    if not ask_yes_no("Proceed with LLM refinement?"):
        print("LLM refinement cancelled.")
        return None
    
    # Progress callback
    def progress_callback(current, total, title):
        bar_length = 30
        progress = current / total
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\r  [{bar}] {current}/{total} - {title[:40]}...", end="", flush=True)
    
    print("\nProcessing records with LLM...")
    refined_records = refine_classification_with_llm(records, progress_callback, model_id=selected_model_id)
    print("\n")
    
    # Save refined results
    llm_output_path = save_llm_refined_results(refined_records, output_path)
    print(f"  ✓ LLM-refined results saved to: {llm_output_path}")
    
    # Print summary
    print("\n--- LLM Refinement Summary ---")
    from collections import Counter
    
    original_topics = Counter(r.topic for r in refined_records)
    final_topics = Counter(getattr(r, 'final_topic', r.topic) for r in refined_records)
    
    changed = sum(1 for r in refined_records 
                  if getattr(r, 'final_topic', r.topic) != r.topic)
    
    print(f"  Model used: {selected_model_id}")
    print(f"  Records changed by LLM: {changed}/{len(refined_records)}")
    print(f"\n  Final topic distribution:")
    for topic, count in sorted(final_topics.items(), key=lambda x: -x[1]):
        print(f"    {topic}: {count}")
    
    return llm_output_path


# ============================================================
# MAIN EXECUTION
# ============================================================

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
    
    records = None
    excel_path = None
    csv_path = None
    
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
    
    # After initial run, ask about LLM refinement
    if records and len(records) > 0:
        print("\n" + "-" * 60)
        print("OPTIONAL: LLM-Based Classification Refinement")
        print("-" * 60)
        print("You can use LM Studio to improve topic classification accuracy.")
        print("This requires LM Studio running locally with a model loaded.")
        
        if ask_yes_no("\nWould you like to refine classifications using LM Studio?"):
            try:
                run_llm_refinement(records, CONFIG['output'])
            except Exception as e:
                print(f"\n✗ LLM refinement error: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("Skipping LLM refinement.")
    
    print("\n" + "=" * 60)
    print("RCT FINDER - Complete")
    print("=" * 60)
