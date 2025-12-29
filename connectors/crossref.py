"""
Crossref connector using the REST API.
"""

import requests
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseConnector
from ..models import RCTRecord
from ..config import CROSSREF_API_URL, RATE_LIMITS
from ..utils import (
    RateLimiter, 
    get_date_range, 
    parse_date, 
    normalize_doi,
    logger
)
from ..detection import detect_rct_from_text


class CrossrefConnector(BaseConnector):
    """Connector for Crossref REST API."""
    
    def __init__(self, mailto: Optional[str] = None):
        self.mailto = mailto or "rct-finder@example.com"
        self.rate_limiter = RateLimiter(RATE_LIMITS['crossref'])
        self.session = requests.Session()
        self.session.headers['User-Agent'] = f'RCTFinder/1.0 (mailto:{self.mailto})'
    
    @property
    def source_name(self) -> str:
        return "Crossref"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _search(
        self, 
        query: str,
        from_date: str,
        until_date: str,
        cursor: str = "*",
        rows: int = 100
    ) -> dict:
        """Execute search query."""
        self.rate_limiter.wait()
        
        params = {
            'query': query,
            'filter': f'from-pub-date:{from_date},until-pub-date:{until_date},type:journal-article',
            'cursor': cursor,
            'rows': rows,
            'select': 'DOI,title,author,abstract,container-title,ISSN,published,publisher,subject,URL,language'
        }
        
        response = self.session.get(CROSSREF_API_URL, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _get_work(self, doi: str) -> dict:
        """Fetch a single work by DOI."""
        self.rate_limiter.wait()
        
        url = f"{CROSSREF_API_URL}/{doi}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def search(
        self, 
        days: int, 
        query: Optional[str] = None,
        max_records: Optional[int] = None,
        include_preprints: bool = False
    ) -> List[str]:
        """Search Crossref for RCT papers."""
        start_date, end_date = get_date_range(days)
        
        # Crossref doesn't have RCT-specific filters, so we search with RCT terms
        search_query = query if query else "randomized controlled trial OR randomised controlled trial OR placebo controlled"
        
        dois = []
        cursor = "*"
        
        while True:
            try:
                result = self._search(search_query, start_date, end_date, cursor)
                
                message = result.get('message', {})
                items = message.get('items', [])
                
                if not items:
                    break
                
                for item in items:
                    doi = item.get('DOI')
                    if doi:
                        # Pre-filter: check if title/abstract contains RCT signals
                        title = ''
                        if item.get('title'):
                            title = item['title'][0] if isinstance(item['title'], list) else item['title']
                        abstract = item.get('abstract', '')
                        
                        is_rct, _ = detect_rct_from_text(title, abstract)
                        if is_rct:
                            dois.append(doi)
                
                if max_records and len(dois) >= max_records:
                    dois = dois[:max_records]
                    break
                
                # Get next cursor
                next_cursor = message.get('next-cursor')
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
                
            except Exception as e:
                logger.error(f"Crossref search error: {e}")
                break
        
        logger.info(f"Crossref found {len(dois)} RCT papers")
        return dois
    
    def fetch_details(self, ids: List[str]) -> List[RCTRecord]:
        """Fetch detailed records for DOIs."""
        records = []
        
        for doi in ids:
            try:
                result = self._get_work(doi)
                record = self._parse_work(result.get('message', {}))
                if record:
                    records.append(record)
            except Exception as e:
                logger.warning(f"Failed to fetch Crossref record {doi}: {e}")
                continue
        
        return records
    
    def _parse_work(self, work: dict) -> Optional[RCTRecord]:
        """Parse Crossref work into RCTRecord."""
        doi = work.get('DOI')
        if not doi:
            return None
        
        doi = normalize_doi(doi)
        
        # Title
        title = ''
        if work.get('title'):
            title = work['title'][0] if isinstance(work['title'], list) else work['title']
        
        # Authors
        authors = []
        for author in work.get('author', []):
            given = author.get('given', '')
            family = author.get('family', '')
            if family:
                full_name = f"{given} {family}".strip()
                authors.append(full_name)
        
        # Abstract (Crossref provides in XML/plain mix)
        abstract = work.get('abstract', '')
        if abstract:
            # Simple cleanup of JATS/XML tags
            import re
            abstract = re.sub(r'<[^>]+>', '', abstract)
        
        # Publication date
        pub_date = None
        pub_year = None
        
        published = work.get('published', {}) or work.get('published-print', {}) or work.get('published-online', {})
        date_parts = published.get('date-parts', [[]])
        if date_parts and date_parts[0]:
            parts = date_parts[0]
            pub_year = parts[0] if len(parts) > 0 else None
            month = parts[1] if len(parts) > 1 else 1
            day = parts[2] if len(parts) > 2 else 1
            if pub_year:
                pub_date = f"{pub_year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
        
        # Journal
        journal = ''
        container = work.get('container-title', [])
        if container:
            journal = container[0] if isinstance(container, list) else container
        
        # ISSN
        issn = None
        issn_list = work.get('ISSN', [])
        if issn_list:
            issn = issn_list[0] if isinstance(issn_list, list) else issn_list
        
        # Publisher
        publisher = work.get('publisher')
        
        # Subject/keywords
        subjects = work.get('subject', [])
        
        # Language
        language = work.get('language')
        
        # URL
        url = work.get('URL') or f"https://doi.org/{doi}"
        
        # RCT detection
        is_rct, detection_method = detect_rct_from_text(title, abstract)
        
        return RCTRecord(
            source_primary="Crossref",
            sources_found_in=["Crossref"],
            doi=doi,
            crossref_doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            issn=issn,
            publication_date=pub_date,
            publication_year=pub_year,
            language=language,
            abstract=abstract,
            keywords=subjects,
            url=url,
            publisher=publisher,
            rct_flag=is_rct,
            rct_detection_method=detection_method,
        )
