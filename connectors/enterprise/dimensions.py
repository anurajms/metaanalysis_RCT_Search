"""
Dimensions connector (requires API key).
"""

import requests
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..base import BaseConnector
from ...models import RCTRecord
from ...config import DIMENSIONS_API_URL, RATE_LIMITS
from ...utils import (
    RateLimiter, 
    get_date_range, 
    parse_date, 
    normalize_doi,
    logger
)
from ...detection import detect_rct_from_text


class DimensionsConnector(BaseConnector):
    """Connector for Dimensions API."""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Dimensions API key is required")
        
        self.api_key = api_key
        self.rate_limiter = RateLimiter(RATE_LIMITS['dimensions'])
        self.session = requests.Session()
        self.session.headers['Authorization'] = f'Bearer {api_key}'
        self.session.headers['Content-Type'] = 'application/json'
    
    @property
    def source_name(self) -> str:
        return "Dimensions"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _query(self, dsl_query: str) -> dict:
        """Execute Dimensions DSL query."""
        self.rate_limiter.wait()
        
        response = self.session.post(
            DIMENSIONS_API_URL,
            json={'query': dsl_query},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    
    def search(
        self, 
        days: int, 
        query: Optional[str] = None,
        max_records: Optional[int] = None,
        include_preprints: bool = False
    ) -> List[str]:
        """Search Dimensions for RCT papers."""
        start_date, end_date = get_date_range(days)
        
        # Build Dimensions DSL query
        conditions = [
            f'date >= "{start_date}"',
            f'date <= "{end_date}"',
            'type = "article"',
        ]
        
        # RCT search
        rct_search = 'title:"randomized controlled trial" OR title:"randomised controlled trial" OR abstract:"randomized controlled trial" OR abstract:"randomised controlled trial"'
        
        if query:
            conditions.append(f'({query})')
        
        limit = max_records or 1000
        
        dsl_query = f'''
            search publications 
            where {' and '.join(conditions)}
            and ({rct_search})
            return publications[id, doi, pmid, pmcid, title, authors, abstract, journal, date, year, publisher]
            limit {limit}
        '''
        
        dim_ids = []
        
        try:
            result = self._query(dsl_query)
            
            publications = result.get('publications', [])
            for pub in publications:
                dim_id = pub.get('id')
                if dim_id:
                    dim_ids.append(dim_id)
            
            logger.info(f"Dimensions found {len(dim_ids)} papers")
            
        except Exception as e:
            logger.error(f"Dimensions search error: {e}")
        
        return dim_ids
    
    def fetch_details(self, ids: List[str]) -> List[RCTRecord]:
        """Fetch detailed records for Dimensions IDs."""
        if not ids:
            return []
        
        # Batch fetch
        ids_str = ', '.join(f'"{id}"' for id in ids[:1000])
        
        dsl_query = f'''
            search publications
            where id in [{ids_str}]
            return publications[id, doi, pmid, pmcid, title, authors, abstract, 
                              journal, date, year, publisher, mesh_terms, 
                              concepts, research_orgs, open_access]
        '''
        
        records = []
        
        try:
            result = self._query(dsl_query)
            
            for pub in result.get('publications', []):
                record = self._parse_publication(pub)
                if record:
                    records.append(record)
                    
        except Exception as e:
            logger.error(f"Dimensions fetch error: {e}")
        
        return records
    
    def _parse_publication(self, pub: dict) -> Optional[RCTRecord]:
        """Parse Dimensions publication into RCTRecord."""
        dim_id = pub.get('id')
        if not dim_id:
            return None
        
        title = pub.get('title', '')
        
        # Authors
        authors = []
        for author in pub.get('authors', []):
            name = author.get('full_name') or author.get('last_name', '')
            if name:
                authors.append(name)
        
        # Abstract
        abstract = pub.get('abstract', '')
        
        # IDs
        doi = normalize_doi(pub.get('doi'))
        pmid = pub.get('pmid')
        pmcid = pub.get('pmcid')
        
        # Publication date
        pub_date = pub.get('date')
        pub_year = pub.get('year')
        
        # Journal
        journal_info = pub.get('journal', {}) or {}
        journal = journal_info.get('title')
        issn = journal_info.get('issn')
        
        # Publisher
        publisher = pub.get('publisher')
        
        # MeSH terms
        mesh_terms = pub.get('mesh_terms', []) or []
        
        # Concepts as fields of study
        concepts = []
        for concept in pub.get('concepts', []):
            if isinstance(concept, str):
                concepts.append(concept)
            elif isinstance(concept, dict):
                concepts.append(concept.get('concept', ''))
        
        # URL
        url = f"https://app.dimensions.ai/details/publication/{dim_id}"
        
        # Open access
        oa = pub.get('open_access', {}) or {}
        if oa.get('is_oa'):
            # Could get OA URL here if available
            pass
        
        # RCT detection
        is_rct, detection_method = detect_rct_from_text(title, abstract)
        
        return RCTRecord(
            source_primary="Dimensions",
            sources_found_in=["Dimensions"],
            dimensions_id=dim_id,
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            title=title,
            authors=authors,
            journal=journal,
            issn=issn,
            publication_date=pub_date,
            publication_year=pub_year,
            abstract=abstract,
            mesh_terms=mesh_terms,
            fields_of_study=concepts,
            url=url,
            publisher=publisher,
            rct_flag=is_rct,
            rct_detection_method=detection_method,
        )
