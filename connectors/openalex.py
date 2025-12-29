"""
OpenAlex connector using the Works API.
"""

import requests
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseConnector
from ..models import RCTRecord
from ..config import OPENALEX_API_URL, RATE_LIMITS, PREPRINT_VENUES
from ..utils import (
    RateLimiter, 
    get_date_range, 
    parse_date, 
    normalize_doi,
    logger
)
from ..detection import detect_rct_from_text


class OpenAlexConnector(BaseConnector):
    """Connector for OpenAlex Works API."""
    
    def __init__(self, mailto: Optional[str] = None):
        self.mailto = mailto or "rct-finder@example.com"
        self.rate_limiter = RateLimiter(RATE_LIMITS['openalex'])
        self.session = requests.Session()
    
    @property
    def source_name(self) -> str:
        return "OpenAlex"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _search(
        self, 
        from_date: str,
        to_date: str,
        search_query: Optional[str] = None,
        cursor: str = "*",
        per_page: int = 100
    ) -> dict:
        """Execute search query."""
        self.rate_limiter.wait()
        
        # Build filter: article type + date range
        filters = [
            'type:article',
            f'from_publication_date:{from_date}',
            f'to_publication_date:{to_date}'
        ]
        
        params = {
            'filter': ','.join(filters),
            'cursor': cursor,
            'per_page': per_page,
            'mailto': self.mailto,
            'select': 'id,doi,title,authorships,publication_date,publication_year,primary_location,concepts,abstract_inverted_index,language,type,is_oa,open_access,ids'
        }
        
        # Add search if provided
        if search_query:
            params['search'] = search_query
        
        response = self.session.get(OPENALEX_API_URL, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _get_work(self, work_id: str) -> dict:
        """Fetch a single work by OpenAlex ID."""
        self.rate_limiter.wait()
        
        url = f"{OPENALEX_API_URL}/{work_id}"
        params = {'mailto': self.mailto}
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def search(
        self, 
        days: int, 
        query: Optional[str] = None,
        max_records: Optional[int] = None,
        include_preprints: bool = False
    ) -> List[str]:
        """Search OpenAlex for RCT papers."""
        start_date, end_date = get_date_range(days)
        
        # Search with RCT terms
        search_query = query if query else "randomized controlled trial OR randomised controlled trial OR placebo controlled"
        
        work_ids = []
        cursor = "*"
        
        while True:
            try:
                result = self._search(start_date, end_date, search_query, cursor)
                
                works = result.get('results', [])
                if not works:
                    break
                
                for work in works:
                    work_id = work.get('id')
                    if work_id:
                        # Filter preprints
                        if not include_preprints:
                            primary_loc = work.get('primary_location', {}) or {}
                            source = primary_loc.get('source', {}) or {}
                            source_type = source.get('type', '')
                            source_name = (source.get('display_name') or '').lower()
                            
                            if source_type == 'repository':
                                # Check if it's a preprint server
                                if any(p in source_name for p in PREPRINT_VENUES):
                                    continue
                        
                        # Pre-filter with RCT detection
                        title = work.get('title', '')
                        abstract = self._reconstruct_abstract(work.get('abstract_inverted_index'))
                        
                        is_rct, _ = detect_rct_from_text(title, abstract)
                        if is_rct:
                            work_ids.append(work_id)
                
                if max_records and len(work_ids) >= max_records:
                    work_ids = work_ids[:max_records]
                    break
                
                # Get next cursor
                meta = result.get('meta', {})
                next_cursor = meta.get('next_cursor')
                if not next_cursor:
                    break
                cursor = next_cursor
                
            except Exception as e:
                logger.error(f"OpenAlex search error: {e}")
                break
        
        logger.info(f"OpenAlex found {len(work_ids)} RCT papers")
        return work_ids
    
    def fetch_details(self, ids: List[str]) -> List[RCTRecord]:
        """Fetch detailed records for OpenAlex IDs."""
        records = []
        
        for work_id in ids:
            try:
                work = self._get_work(work_id)
                record = self._parse_work(work)
                if record:
                    records.append(record)
            except Exception as e:
                logger.warning(f"Failed to fetch OpenAlex record {work_id}: {e}")
                continue
        
        return records
    
    def _reconstruct_abstract(self, inverted_index: Optional[dict]) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return ""
        
        # Build position -> word mapping
        positions = {}
        for word, indices in inverted_index.items():
            for idx in indices:
                positions[idx] = word
        
        # Reconstruct text
        if not positions:
            return ""
        
        max_pos = max(positions.keys())
        words = [positions.get(i, '') for i in range(max_pos + 1)]
        return ' '.join(words)
    
    def _parse_work(self, work: dict) -> Optional[RCTRecord]:
        """Parse OpenAlex work into RCTRecord."""
        work_id = work.get('id')
        if not work_id:
            return None
        
        # Extract OpenAlex ID (just the identifier part)
        openalex_id = work_id.replace('https://openalex.org/', '')
        
        # DOI
        doi = normalize_doi(work.get('doi'))
        
        # Title
        title = work.get('title', '')
        
        # Authors
        authors = []
        for authorship in work.get('authorships', []):
            author = authorship.get('author', {})
            name = author.get('display_name')
            if name:
                authors.append(name)
        
        # Abstract
        abstract = self._reconstruct_abstract(work.get('abstract_inverted_index'))
        
        # Publication date
        pub_date = work.get('publication_date')
        pub_year = work.get('publication_year')
        
        # External IDs
        ids = work.get('ids', {}) or {}
        pmid = ids.get('pmid')
        if pmid:
            pmid = pmid.replace('https://pubmed.ncbi.nlm.nih.gov/', '')
        pmcid = ids.get('pmcid')
        
        # Journal/source
        journal = None
        issn = None
        publisher = None
        
        primary_loc = work.get('primary_location', {}) or {}
        source = primary_loc.get('source', {}) or {}
        if source:
            journal = source.get('display_name')
            issn_list = source.get('issn', [])
            if issn_list:
                issn = issn_list[0] if isinstance(issn_list, list) else issn_list
            publisher = source.get('host_organization_name')
        
        # Concepts/fields of study
        fields_of_study = []
        for concept in work.get('concepts', []):
            name = concept.get('display_name')
            if name:
                fields_of_study.append(name)
        
        # Language
        language = work.get('language')
        
        # URL
        url = work.get('id')
        
        # Check for open access PDF
        oa = work.get('open_access', {}) or {}
        if oa.get('is_oa') and oa.get('oa_url'):
            url = oa['oa_url']
        
        # Check if preprint
        source_type = source.get('type', '')
        is_preprint = source_type == 'repository'
        
        # RCT detection
        is_rct, detection_method = detect_rct_from_text(title, abstract)
        
        return RCTRecord(
            source_primary="OpenAlex",
            sources_found_in=["OpenAlex"],
            openalex_id=openalex_id,
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            title=title,
            authors=authors,
            journal=journal,
            issn=issn,
            publication_date=pub_date,
            publication_year=pub_year,
            language=language,
            abstract=abstract,
            fields_of_study=fields_of_study,
            url=url,
            publisher=publisher,
            is_preprint=is_preprint,
            rct_flag=is_rct,
            rct_detection_method=detection_method,
        )
