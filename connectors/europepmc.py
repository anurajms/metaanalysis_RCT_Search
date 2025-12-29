"""
Europe PMC connector using the REST API.
"""

import requests
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseConnector
from ..models import RCTRecord
from ..config import EUROPEPMC_API_URL, RATE_LIMITS
from ..utils import (
    RateLimiter, 
    get_date_range, 
    parse_date, 
    normalize_doi,
    logger
)
from ..detection import detect_rct_from_text


class EuropePMCConnector(BaseConnector):
    """Connector for Europe PMC REST API."""
    
    def __init__(self):
        self.rate_limiter = RateLimiter(RATE_LIMITS['europepmc'])
        self.session = requests.Session()
    
    @property
    def source_name(self) -> str:
        return "EuropePMC"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _search(
        self, 
        query: str, 
        cursor: str = "*",
        page_size: int = 100
    ) -> dict:
        """Execute search query."""
        self.rate_limiter.wait()
        
        params = {
            'query': query,
            'resultType': 'core',
            'cursorMark': cursor,
            'pageSize': page_size,
            'format': 'json',
            'sort': 'FIRST_PDATE desc'
        }
        
        response = self.session.get(EUROPEPMC_API_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def search(
        self, 
        days: int, 
        query: Optional[str] = None,
        max_records: Optional[int] = None,
        include_preprints: bool = False
    ) -> List[str]:
        """Search Europe PMC for RCT papers."""
        start_date, end_date = get_date_range(days)
        
        # Build query with date filter and RCT publication type
        query_parts = [
            f'(FIRST_PDATE:[{start_date} TO {end_date}])',
            '(PUB_TYPE:"randomized controlled trial" OR PUB_TYPE:"Randomized Controlled Trial")'
        ]
        
        if query:
            query_parts.append(f'({query})')
        
        # Filter preprints
        if not include_preprints:
            query_parts.append('(SRC:MED OR SRC:PMC)')  # Only MEDLINE and PMC indexed
        
        full_query = ' AND '.join(query_parts)
        
        paper_ids = []
        cursor = "*"
        
        while True:
            try:
                result = self._search(full_query, cursor)
                
                results_list = result.get('resultList', {}).get('result', [])
                if not results_list:
                    break
                
                for paper in results_list:
                    # Create a compound ID
                    pmid = paper.get('pmid')
                    pmcid = paper.get('pmcid')
                    
                    if pmid:
                        paper_ids.append(f"pmid:{pmid}")
                    elif pmcid:
                        paper_ids.append(f"pmcid:{pmcid}")
                
                if max_records and len(paper_ids) >= max_records:
                    paper_ids = paper_ids[:max_records]
                    break
                
                # Check for next cursor
                next_cursor = result.get('nextCursorMark')
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
                
            except Exception as e:
                logger.error(f"Europe PMC search error: {e}")
                break
        
        logger.info(f"Europe PMC found {len(paper_ids)} papers")
        return paper_ids
    
    def fetch_details(self, ids: List[str]) -> List[RCTRecord]:
        """Fetch detailed records. IDs are in format 'pmid:123' or 'pmcid:PMC123'."""
        records = []
        
        for paper_id in ids:
            try:
                record = self._fetch_single(paper_id)
                if record:
                    records.append(record)
            except Exception as e:
                logger.warning(f"Failed to fetch Europe PMC record {paper_id}: {e}")
                continue
        
        return records
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _fetch_single(self, paper_id: str) -> Optional[RCTRecord]:
        """Fetch a single paper by ID."""
        self.rate_limiter.wait()
        
        # Parse ID type
        if paper_id.startswith('pmid:'):
            query = f'EXT_ID:{paper_id[5:]} AND SRC:MED'
        elif paper_id.startswith('pmcid:'):
            query = f'PMCID:{paper_id[6:]}'
        else:
            query = paper_id
        
        params = {
            'query': query,
            'resultType': 'core',
            'format': 'json'
        }
        
        response = self.session.get(EUROPEPMC_API_URL, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        results = data.get('resultList', {}).get('result', [])
        
        if not results:
            return None
        
        return self._parse_paper(results[0])
    
    def _parse_paper(self, paper: dict) -> Optional[RCTRecord]:
        """Parse Europe PMC result into RCTRecord."""
        pmid = paper.get('pmid')
        pmcid = paper.get('pmcid')
        
        if not pmid and not pmcid:
            return None
        
        title = paper.get('title', '')
        
        # Authors
        authors = []
        author_list = paper.get('authorList', {}).get('author', [])
        for author in author_list:
            full_name = author.get('fullName')
            if full_name:
                authors.append(full_name)
        
        # Abstract
        abstract = paper.get('abstractText')
        
        # Publication date
        pub_date = None
        pub_year = None
        
        first_pub_date = paper.get('firstPublicationDate')
        if first_pub_date:
            pub_date, pub_year = parse_date(first_pub_date)
        
        if not pub_year:
            pub_year = paper.get('pubYear')
            if pub_year:
                pub_year = int(pub_year)
        
        # DOI
        doi = normalize_doi(paper.get('doi'))
        
        # Journal
        journal = paper.get('journalTitle')
        issn = paper.get('journalIssn')
        
        # Keywords/MeSH
        keywords = paper.get('keywordList', {}).get('keyword', [])
        mesh_terms = []
        for mesh in paper.get('meshHeadingList', {}).get('meshHeading', []):
            term = mesh.get('descriptorName')
            if term:
                mesh_terms.append(term)
        
        # Language
        language = paper.get('language')
        
        # Publisher
        publisher = paper.get('publisherLocation')
        
        # Publication type
        pub_types = paper.get('pubTypeList', {}).get('pubType', [])
        is_rct = 'randomized controlled trial' in [pt.lower() for pt in pub_types]
        
        if is_rct:
            detection_method = "Europe PMC publication type filter"
        else:
            is_rct, detection_method = detect_rct_from_text(title, abstract)
        
        # URL
        url = None
        if pmid:
            url = f"https://europepmc.org/article/MED/{pmid}"
        elif pmcid:
            url = f"https://europepmc.org/article/PMC/{pmcid}"
        
        return RCTRecord(
            source_primary="EuropePMC",
            sources_found_in=["EuropePMC"],
            pmid=pmid,
            pmcid=pmcid,
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            issn=issn,
            publication_date=pub_date,
            publication_year=pub_year,
            language=language,
            abstract=abstract,
            mesh_terms=mesh_terms,
            keywords=keywords,
            url=url,
            publisher=publisher,
            rct_flag=is_rct,
            rct_detection_method=detection_method,
        )
