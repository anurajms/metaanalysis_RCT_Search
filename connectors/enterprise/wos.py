"""
Web of Science connector (requires API key).

Note: WoS API access requires institutional subscription.
"""

import requests
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..base import BaseConnector
from ...models import RCTRecord
from ...config import WOS_API_URL, RATE_LIMITS
from ...utils import (
    RateLimiter, 
    get_date_range, 
    parse_date, 
    normalize_doi,
    logger
)
from ...detection import detect_rct_from_text


class WoSConnector(BaseConnector):
    """Connector for Web of Science API."""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Web of Science API key is required")
        
        self.api_key = api_key
        self.rate_limiter = RateLimiter(RATE_LIMITS['wos'])
        self.session = requests.Session()
        self.session.headers['X-ApiKey'] = api_key
        self.session.headers['Accept'] = 'application/json'
    
    @property
    def source_name(self) -> str:
        return "WebOfScience"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _search(
        self, 
        query: str, 
        first_record: int = 1,
        count: int = 100
    ) -> dict:
        """Execute WoS search."""
        self.rate_limiter.wait()
        
        # WoS Starter API endpoint
        url = f"{WOS_API_URL}/wos/search"
        
        params = {
            'databaseId': 'WOS',
            'usrQuery': query,
            'firstRecord': first_record,
            'count': min(count, 100)
        }
        
        response = self.session.get(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    
    def search(
        self, 
        days: int, 
        query: Optional[str] = None,
        max_records: Optional[int] = None,
        include_preprints: bool = False
    ) -> List[str]:
        """Search Web of Science for RCT papers."""
        from datetime import datetime, timedelta, timezone
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Build WoS query
        date_range = f'{start_date.strftime("%Y-%m-%d")}/{end_date.strftime("%Y-%m-%d")}'
        
        query_parts = [
            f'PY=({start_date.year}-{end_date.year})',
            'DT=(Article)',
            'TS=("randomized controlled trial" OR "randomised controlled trial" OR "RCT" OR "placebo-controlled")'
        ]
        
        if query:
            query_parts.append(f'TS=({query})')
        
        full_query = ' AND '.join(query_parts)
        
        wos_ids = []
        first_record = 1
        
        while True:
            try:
                result = self._search(full_query, first_record)
                
                records = result.get('Data', {}).get('Records', {}).get('records', {}).get('REC', [])
                
                if not records:
                    break
                
                # Handle single result case
                if isinstance(records, dict):
                    records = [records]
                
                for record in records:
                    uid = record.get('UID', '')
                    if uid:
                        wos_ids.append(uid)
                
                if max_records and len(wos_ids) >= max_records:
                    wos_ids = wos_ids[:max_records]
                    break
                
                # Check for more results
                query_result = result.get('QueryResult', {})
                records_found = query_result.get('RecordsFound', 0)
                
                first_record += len(records)
                if first_record > records_found:
                    break
                    
            except Exception as e:
                logger.error(f"Web of Science search error: {e}")
                break
        
        logger.info(f"Web of Science found {len(wos_ids)} papers")
        return wos_ids
    
    def fetch_details(self, ids: List[str]) -> List[RCTRecord]:
        """Fetch detailed records for WoS UIDs."""
        records = []
        
        # WoS doesn't have a batch fetch, so we re-search for each ID
        for wos_id in ids:
            try:
                result = self._search(f'UT={wos_id}', count=1)
                
                recs = result.get('Data', {}).get('Records', {}).get('records', {}).get('REC', [])
                if recs:
                    rec = recs[0] if isinstance(recs, list) else recs
                    record = self._parse_record(rec)
                    if record:
                        records.append(record)
                        
            except Exception as e:
                logger.warning(f"Failed to fetch WoS record {wos_id}: {e}")
                continue
        
        return records
    
    def _parse_record(self, rec: dict) -> Optional[RCTRecord]:
        """Parse WoS record into RCTRecord."""
        uid = rec.get('UID', '')
        
        static_data = rec.get('static_data', {})
        summary = static_data.get('summary', {})
        
        # Title
        titles = summary.get('titles', {}).get('title', [])
        title = ''
        for t in titles:
            if t.get('@type') == 'item':
                title = t.get('content', '')
                break
        
        # Authors
        authors = []
        names = summary.get('names', {}).get('name', [])
        if isinstance(names, dict):
            names = [names]
        for name in names:
            full_name = name.get('full_name', '')
            if full_name:
                authors.append(full_name)
        
        # Abstract
        abstract = ''
        abstracts = static_data.get('fullrecord_metadata', {}).get('abstracts', {}).get('abstract', {})
        if abstracts:
            abstract_text = abstracts.get('abstract_text', {})
            if isinstance(abstract_text, dict):
                abstract = abstract_text.get('p', '')
            else:
                abstract = abstract_text
        
        # DOI
        doi = None
        identifiers = summary.get('identifier', [])
        if isinstance(identifiers, dict):
            identifiers = [identifiers]
        for ident in identifiers:
            if ident.get('@type') == 'doi':
                doi = normalize_doi(ident.get('@value'))
                break
        
        # Publication date
        pub_date = None
        pub_year = None
        pub_info = summary.get('pub_info', {})
        if pub_info:
            pub_year = pub_info.get('@pubyear')
            if pub_year:
                pub_year = int(pub_year)
                pub_date = f"{pub_year}-01-01"
        
        # Journal
        journal = None
        sources = summary.get('titles', {}).get('title', [])
        for s in sources:
            if s.get('@type') == 'source':
                journal = s.get('content', '')
                break
        
        # Publisher
        publisher_info = summary.get('publishers', {}).get('publisher', {})
        publisher = None
        if publisher_info:
            names = publisher_info.get('names', {}).get('name', {})
            if names:
                publisher = names.get('full_name', '')
        
        # RCT detection
        is_rct, detection_method = detect_rct_from_text(title, abstract)
        
        return RCTRecord(
            source_primary="WebOfScience",
            sources_found_in=["WebOfScience"],
            wos_id=uid,
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            publication_date=pub_date,
            publication_year=pub_year,
            abstract=abstract,
            publisher=publisher,
            rct_flag=is_rct,
            rct_detection_method=detection_method,
        )
