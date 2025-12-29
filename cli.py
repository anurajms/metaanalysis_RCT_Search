"""
CLI interface for RCT Finder.
"""

import argparse
import os
import sys

from .config import DEFAULT_DAYS, DEFAULT_OUTPUT, get_api_key


def parse_args(args=None):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='rct_finder',
        description='Find randomized controlled trials (RCTs) published in the last N days across major medical journals.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m rct_finder --days 30 --output results.xlsx
  python -m rct_finder --days 7 --ncbi-api-key YOUR_KEY --semantic-scholar-api-key YOUR_KEY
  python -m rct_finder --days 14 --max-records-per-source 100 --include-preprints

Environment variables:
  NCBI_API_KEY              - PubMed/NCBI API key
  SEMANTIC_SCHOLAR_API_KEY  - Semantic Scholar API key
  SCOPUS_API_KEY            - Scopus (Elsevier) API key
  WOS_API_KEY               - Web of Science API key
  DIMENSIONS_API_KEY        - Dimensions API key
"""
    )
    
    # Core options
    parser.add_argument(
        '--days', '-d',
        type=int,
        default=DEFAULT_DAYS,
        help=f'Number of days to look back (default: {DEFAULT_DAYS})'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=DEFAULT_OUTPUT,
        help=f'Output Excel file path (default: {DEFAULT_OUTPUT}). CSV will be created with same name.'
    )
    
    parser.add_argument(
        '--max-records-per-source',
        type=int,
        default=None,
        help='Maximum records to retrieve per source (default: no limit)'
    )
    
    parser.add_argument(
        '--include-preprints',
        action='store_true',
        default=False,
        help='Include preprints in results (default: false)'
    )
    
    # API keys
    parser.add_argument(
        '--ncbi-api-key',
        type=str,
        default=None,
        help='NCBI/PubMed API key (or set NCBI_API_KEY env var)'
    )
    
    parser.add_argument(
        '--semantic-scholar-api-key',
        type=str,
        default=None,
        help='Semantic Scholar API key (or set SEMANTIC_SCHOLAR_API_KEY env var)'
    )
    
    parser.add_argument(
        '--scopus-api-key',
        type=str,
        default=None,
        help='Scopus (Elsevier) API key (or set SCOPUS_API_KEY env var)'
    )
    
    parser.add_argument(
        '--wos-api-key',
        type=str,
        default=None,
        help='Web of Science API key (or set WOS_API_KEY env var)'
    )
    
    parser.add_argument(
        '--dimensions-api-key',
        type=str,
        default=None,
        help='Dimensions API key (or set DIMENSIONS_API_KEY env var)'
    )
    
    # Additional options
    parser.add_argument(
        '--scrape-fallback',
        action='store_true',
        default=True,
        help='Enable web scraping fallback for sources without APIs (default: true)'
    )
    
    parser.add_argument(
        '--no-scrape-fallback',
        action='store_false',
        dest='scrape_fallback',
        help='Disable web scraping fallback'
    )
    
    parser.add_argument(
        '--query', '-q',
        type=str,
        default=None,
        help='Additional search query terms to filter results'
    )
    
    parser.add_argument(
        '--sources',
        type=str,
        nargs='+',
        default=None,
        choices=['pubmed', 'semanticscholar', 'europepmc', 'crossref', 'openalex', 
                 'scopus', 'wos', 'dimensions'],
        help='Specific sources to query (default: all available)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        default=False,
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--use-llm-classifier',
        action='store_true',
        default=False,
        help='Use LLM for topic classification (requires additional setup)'
    )
    
    return parser.parse_args(args)


def get_config_from_args(args):
    """Build configuration dictionary from parsed arguments."""
    return {
        'days': args.days,
        'output': args.output,
        'max_records_per_source': args.max_records_per_source,
        'include_preprints': args.include_preprints,
        'query': args.query,
        'sources': args.sources,
        'scrape_fallback': args.scrape_fallback,
        'verbose': args.verbose,
        'use_llm_classifier': args.use_llm_classifier,
        'api_keys': {
            'ncbi': get_api_key('ncbi', args.ncbi_api_key),
            'semantic_scholar': get_api_key('semantic_scholar', args.semantic_scholar_api_key),
            'scopus': get_api_key('scopus', args.scopus_api_key),
            'wos': get_api_key('wos', args.wos_api_key),
            'dimensions': get_api_key('dimensions', args.dimensions_api_key),
        }
    }
