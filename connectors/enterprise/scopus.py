"""
Scopus connector using Elsevier APIs (requires API key).
"""

import requests
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..base import BaseConnector
from ...models import RCTRecord
from ...config import SCOPUS_API_URL, RATE_LIMITS
from ...utils import (
    RateLimiter, 
    get_date_range, 
    parse_date, 
    normalize_doi,
    logger
)
from ...detection import detect_rct_from_text


class ScopusConnector(BaseConnector):
    """Connector for Scopus API (Elsevier)."""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Scopus API key is required")
        
        self.api_key = api_key
        self.rate_limiter = RateLimiter(RATE_LIMITS['scopus'])
        self.session = requests.Session()
        self.session.headers['X-ELS-APIKey'] = api_key
        self.session.headers['Accept'] = 'application/json'
    
    @property
    def source_name(self) -> str:
        return "Scopus"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _search(self, query: str, start: int = 0, count: int = 25) -> dict:
        """Execute Scopus search."""
        self.rate_limiter.wait()
        
        params = {
            'query': query,
            'start': start,
            'count': min(count, 25),  # Scopus limits to 25 per page
            'view': 'COMPLETE'
        }
        
        response = self.session.get(SCOPUS_API_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def search(
        self, 
        days: int, 
        query: Optional[str] = None,
        max_records: Optional[int] = None,
        include_preprints: bool = False
    ) -> List[str]:
        """Search Scopus for RCT papers."""
        start_date, end_date = get_date_range(days)
        
        # Build Scopus query
        query_parts = [
            f'PUBYEAR > {int(start_date[:4]) - 1}',
            'DOCTYPE(ar)',  # Articles only
            '(TITLE-ABS-KEY("randomized controlled trial") OR TITLE-ABS-KEY("randomised controlled trial") OR TITLE-ABS-KEY(RCT) OR TITLE-ABS-KEY("placebo-controlled"))'
        ]
        
        if query:
            query_parts.append(f'({query})')
        
        full_query = ' AND '.join(query_parts)
        
        scopus_ids = []
        start = 0
        
        while True:
            try:
                result = self._search(full_query, start)
                
                search_results = result.get('search-results', {})
                entries = search_results.get('entry', [])
                
                if not entries:
                    break
                
                for entry in entries:
                    if entry.get('error'):
                        continue
                    
                    scopus_id = entry.get('dc:identifier', '')
                    if scopus_id.startswith('SCOPUS_ID:'):
                        scopus_id = scopus_id[10:]
                    
                    if scopus_id:
                        scopus_ids.append(scopus_id)
                
                if max_records and len(scopus_ids) >= max_records:
                    scopus_ids = scopus_ids[:max_records]
                    break
                
                # Check for more results
                total = int(search_results.get('opensearch:totalResults', 0))
                start += len(entries)
                
                if start >= total:
                    break
                    
            except Exception as e:
                logger.error(f"Scopus search error: {e}")
                break
        
        logger.info(f"Scopus found {len(scopus_ids)} papers")
        return scopus_ids
    
    def fetch_details(self, ids: List[str]) -> List[RCTRecord]:
        """Fetch detailed records for Scopus IDs."""
        records = []
        
        for scopus_id in ids:
            try:
                record = self._fetch_single(scopus_id)
                if record:
                    records.append(record)
            except Exception as e:
                logger.warning(f"Failed to fetch Scopus record {scopus_id}: {e}")
                continue
        
        return records
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _fetch_single(self, scopus_id: str) -> Optional[RCTRecord]:
        """Fetch a single record from Scopus."""
        self.rate_limiter.wait()
        
        # Search for the specific ID
        result = self._search(f'EID({scopus_id})')
        
        entries = result.get('search-results', {}).get('entry', [])
        if not entries or entries[0].get('error'):
            return None
        
        return self._parse_entry(entries[0])
    
    def _parse_entry(self, entry: dict) -> Optional[RCTRecord]:
        """Parse Scopus entry into RCTRecord."""
        scopus_id = entry.get('dc:identifier', '').replace('SCOPUS_ID:', '')
        
        title = entry.get('dc:title', '')
        
        # Authors
        authors = []
        author_str = entry.get('dc:creator')
        if author_str:
            authors = [a.strip() for a in author_str.split(';') if a.strip()]
        
        # Abstract
        abstract = entry.get('dc:description', '')
        
        # DOI
        doi = normalize_doi(entry.get('prism:doi'))
        
        # Publication date
        pub_date = entry.get('prism:coverDate')
        pub_year = None
        if pub_date:
            _, pub_year = parse_date(pub_date)
        
        # Journal
        journal = entry.get('prism:publicationName')
        issn = entry.get('prism:issn')
        
        # Publisher
        publisher = entry.get('prism:publisher')
        
        # URL
        url = None
        for link in entry.get('link', []):
            if link.get('@ref') == 'scopus':
                url = link.get('@href')
                break
        
        # RCT detection
        is_rct, detection_method = detect_rct_from_text(title, abstract)
        
        return RCTRecord(
            source_primary="Scopus",
            sources_found_in=["Scopus"],
            scopus_id=scopus_id,
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            issn=issn,
            publication_date=pub_date,
            publication_year=pub_year,
            abstract=abstract,
            url=url,
            publisher=publisher,
            rct_flag=is_rct,
            rct_detection_method=detection_method,
        )
