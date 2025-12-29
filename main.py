"""
Main orchestrator for RCT Finder.
"""

import logging
from typing import List, Dict, Optional
from collections import Counter

from .models import RCTRecord
from .connectors.pubmed import PubMedConnector
from .connectors.semantic_scholar import SemanticScholarConnector
from .connectors.europepmc import EuropePMCConnector
from .connectors.crossref import CrossrefConnector
from .connectors.openalex import OpenAlexConnector
from .deduplication import deduplicate_records
from .classification import classify_records
from .output import save_outputs
from .utils import logger


class RCTFinder:
    """Main orchestrator for finding RCTs across multiple sources."""
    
    def __init__(self, config: Dict):
        """
        Initialize the RCT Finder.
        
        Args:
            config: Configuration dictionary from CLI
        """
        self.config = config
        self.days = config['days']
        self.max_records = config['max_records_per_source']
        self.include_preprints = config['include_preprints']
        self.query = config.get('query')
        self.api_keys = config.get('api_keys', {})
        self.verbose = config.get('verbose', False)
        self.use_llm = config.get('use_llm_classifier', False)
        
        # Set logging level
        if self.verbose:
            logger.setLevel(logging.DEBUG)
        
        # Initialize connectors
        self.connectors = []
        self._init_connectors(config.get('sources'))
        
        # Statistics
        self.stats = {
            'per_source': {},
            'total_retrieved': 0,
            'deduplicated': 0,
            'excluded': Counter(),
            'by_topic': Counter(),
        }
    
    def _init_connectors(self, sources: Optional[List[str]]):
        """Initialize data source connectors."""
        # Default connectors (always available)
        all_connectors = {
            'pubmed': lambda: PubMedConnector(self.api_keys.get('ncbi')),
            'semanticscholar': lambda: SemanticScholarConnector(self.api_keys.get('semantic_scholar')),
            'europepmc': lambda: EuropePMCConnector(),
            'crossref': lambda: CrossrefConnector(),
            'openalex': lambda: OpenAlexConnector(),
        }
        
        # Enterprise connectors (require API keys)
        if self.api_keys.get('scopus'):
            try:
                from .connectors.enterprise.scopus import ScopusConnector
                all_connectors['scopus'] = lambda: ScopusConnector(self.api_keys['scopus'])
            except ImportError:
                logger.warning("Scopus connector not available")
        
        if self.api_keys.get('wos'):
            try:
                from .connectors.enterprise.wos import WoSConnector
                all_connectors['wos'] = lambda: WoSConnector(self.api_keys['wos'])
            except ImportError:
                logger.warning("Web of Science connector not available")
        
        if self.api_keys.get('dimensions'):
            try:
                from .connectors.enterprise.dimensions import DimensionsConnector
                all_connectors['dimensions'] = lambda: DimensionsConnector(self.api_keys['dimensions'])
            except ImportError:
                logger.warning("Dimensions connector not available")
        
        # Select connectors
        if sources:
            selected = [s.lower() for s in sources]
        else:
            # Use all core connectors + enterprise if keys provided
            selected = ['pubmed', 'semanticscholar', 'europepmc', 'crossref', 'openalex']
            if self.api_keys.get('scopus'):
                selected.append('scopus')
            if self.api_keys.get('wos'):
                selected.append('wos')
            if self.api_keys.get('dimensions'):
                selected.append('dimensions')
        
        for source in selected:
            if source in all_connectors:
                try:
                    connector = all_connectors[source]()
                    self.connectors.append(connector)
                    logger.info(f"Initialized connector: {connector.source_name}")
                except Exception as e:
                    logger.error(f"Failed to initialize {source} connector: {e}")
    
    def run(self) -> List[RCTRecord]:
        """
        Run the RCT finder pipeline.
        
        Returns:
            List of deduplicated RCTRecord objects
        """
        all_records = []
        
        # Query each source
        for connector in self.connectors:
            source_name = connector.source_name
            logger.info(f"Querying {source_name}...")
            
            try:
                records = connector.search_and_fetch(
                    days=self.days,
                    query=self.query,
                    max_records=self.max_records,
                    include_preprints=self.include_preprints
                )
                
                # Filter non-RCT records
                rct_records = [r for r in records if r.rct_flag]
                non_rct_count = len(records) - len(rct_records)
                
                if non_rct_count > 0:
                    self.stats['excluded']['not_rct'] += non_rct_count
                
                # Filter preprints if needed
                if not self.include_preprints:
                    before = len(rct_records)
                    rct_records = [r for r in rct_records if not r.is_preprint]
                    preprint_count = before - len(rct_records)
                    if preprint_count > 0:
                        self.stats['excluded']['preprint'] += preprint_count
                
                self.stats['per_source'][source_name] = len(rct_records)
                all_records.extend(rct_records)
                
                logger.info(f"{source_name}: Retrieved {len(rct_records)} RCT records")
                
            except Exception as e:
                logger.error(f"Error querying {source_name}: {e}")
                self.stats['per_source'][source_name] = 0
                continue
        
        self.stats['total_retrieved'] = len(all_records)
        
        # Deduplicate
        logger.info("Deduplicating records...")
        deduplicated = deduplicate_records(all_records)
        self.stats['deduplicated'] = len(deduplicated)
        
        # Classify topics
        logger.info("Classifying topics...")
        classified = classify_records(deduplicated, use_llm=self.use_llm)
        
        # Count by topic
        for record in classified:
            self.stats['by_topic'][record.topic] += 1
        
        return classified
    
    def save_results(self, records: List[RCTRecord], output_path: str):
        """Save results to Excel and CSV files."""
        return save_outputs(records, output_path)
    
    def print_summary(self):
        """Print run summary to console."""
        print("\n" + "=" * 60)
        print("RCT FINDER - RUN SUMMARY")
        print("=" * 60)
        
        print(f"\nSearch window: Last {self.days} days")
        print(f"Include preprints: {self.include_preprints}")
        
        print("\n--- Records Retrieved Per Source ---")
        for source, count in sorted(self.stats['per_source'].items()):
            print(f"  {source}: {count}")
        
        print(f"\n--- Totals ---")
        print(f"  Total retrieved: {self.stats['total_retrieved']}")
        print(f"  After deduplication: {self.stats['deduplicated']}")
        
        if self.stats['excluded']:
            print(f"\n--- Excluded ---")
            for reason, count in sorted(self.stats['excluded'].items()):
                print(f"  {reason}: {count}")
        
        print(f"\n--- By Topic ---")
        for topic, count in sorted(self.stats['by_topic'].items()):
            print(f"  {topic}: {count}")
        
        print("\n" + "=" * 60)


def run_finder(config: Dict) -> tuple:
    """
    Main entry point for running the RCT finder.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Tuple of (records, excel_path, csv_path)
    """
    finder = RCTFinder(config)
    
    # Run the pipeline
    records = finder.run()
    
    # Save results
    excel_path, csv_path = finder.save_results(records, config['output'])
    
    # Print summary
    finder.print_summary()
    
    print(f"\nResults saved to:")
    print(f"  Excel: {excel_path}")
    print(f"  CSV: {csv_path}")
    
    return records, excel_path, csv_path
