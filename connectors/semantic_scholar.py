"""
Semantic Scholar connector using the Academic Graph API.
"""

import requests
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseConnector
from ..models import RCTRecord
from ..config import SEMANTIC_SCHOLAR_API_URL, RATE_LIMITS, PREPRINT_VENUES
from ..utils import (
    RateLimiter, 
    get_date_range, 
    parse_date, 
    normalize_doi,
    chunk_list,
    logger
)
from ..detection import detect_rct_from_text


class SemanticScholarConnector(BaseConnector):
    """Connector for Semantic Scholar Academic Graph API."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.rate_limiter = RateLimiter(RATE_LIMITS['semantic_scholar'])
        self.session = requests.Session()
        if api_key:
            self.session.headers['x-api-key'] = api_key
    
    @property
    def source_name(self) -> str:
        return "SemanticScholar"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _search_papers(
        self, 
        query: str, 
        year_range: str,
        offset: int = 0,
        limit: int = 100
    ) -> dict:
        """Search for papers using the bulk search endpoint."""
        self.rate_limiter.wait()
        
        url = f"{SEMANTIC_SCHOLAR_API_URL}/paper/search"
        params = {
            'query': query,
            'year': year_range,
            'offset': offset,
            'limit': min(limit, 100),
            'fields': 'paperId,title,authors,abstract,venue,publicationDate,year,externalIds,fieldsOfStudy,publicationTypes,journal,isOpenAccess,openAccessPdf'
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _get_paper_details(self, paper_ids: List[str]) -> List[dict]:
        """Fetch detailed paper information using batch endpoint."""
        self.rate_limiter.wait()
        
        url = f"{SEMANTIC_SCHOLAR_API_URL}/paper/batch"
        params = {
            'fields': 'paperId,title,authors,abstract,venue,publicationDate,year,externalIds,fieldsOfStudy,publicationTypes,journal,isOpenAccess,openAccessPdf,citationCount,referenceCount'
        }
        
        response = self.session.post(
            url, 
            params=params,
            json={'ids': paper_ids},
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
        """Search Semantic Scholar for RCT papers."""
        from datetime import datetime, timedelta, timezone
        
        # Calculate year range (S2 only supports year filtering)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # If spanning years, use range
        if start_date.year == end_date.year:
            year_range = str(end_date.year)
        else:
            year_range = f"{start_date.year}-{end_date.year}"
        
        # Build search query with RCT terms
        rct_query = query if query else "randomized controlled trial OR randomised controlled trial OR RCT OR placebo-controlled"
        
        paper_ids = []
        offset = 0
        limit = min(max_records, 100) if max_records else 100
        
        while True:
            try:
                result = self._search_papers(rct_query, year_range, offset, limit)
                
                papers = result.get('data', [])
                if not papers:
                    break
                
                for paper in papers:
                    paper_id = paper.get('paperId')
                    if paper_id:
                        # Filter by publication date within our window
                        pub_date = paper.get('publicationDate')
                        if pub_date:
                            try:
                                paper_date = datetime.strptime(pub_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                                if paper_date < start_date:
                                    continue
                            except ValueError:
                                pass
                        
                        # Filter preprints if needed
                        if not include_preprints:
                            venue = (paper.get('venue') or '').lower()
                            if any(preprint in venue for preprint in PREPRINT_VENUES):
                                continue
                        
                        paper_ids.append(paper_id)
                
                if max_records and len(paper_ids) >= max_records:
                    paper_ids = paper_ids[:max_records]
                    break
                
                # Check if there are more results
                total = result.get('total', 0)
                offset += len(papers)
                if offset >= total:
                    break
                    
            except Exception as e:
                logger.error(f"Semantic Scholar search error: {e}")
                break
        
        logger.info(f"Semantic Scholar found {len(paper_ids)} papers")
        return paper_ids
    
    def fetch_details(self, ids: List[str]) -> List[RCTRecord]:
        """Fetch detailed records for paper IDs."""
        records = []
        
        # Process in chunks (batch API limit is 500)
        for chunk in chunk_list(ids, 500):
            try:
                papers = self._get_paper_details(chunk)
                for paper in papers:
                    if paper:  # Skip null entries
                        record = self._parse_paper(paper)
                        if record:
                            records.append(record)
            except Exception as e:
                logger.error(f"Failed to fetch Semantic Scholar details: {e}")
                continue
        
        return records
    
    def _parse_paper(self, paper: dict) -> Optional[RCTRecord]:
        """Parse a Semantic Scholar paper into an RCTRecord."""
        paper_id = paper.get('paperId')
        if not paper_id:
            return None
        
        title = paper.get('title', '')
        
        # Authors
        authors = []
        for author in paper.get('authors', []):
            name = author.get('name')
            if name:
                authors.append(name)
        
        # Abstract
        abstract = paper.get('abstract')
        
        # Publication date
        pub_date = paper.get('publicationDate')
        pub_year = paper.get('year')
        if pub_date:
            parsed_date, parsed_year = parse_date(pub_date)
            if parsed_date:
                pub_date = parsed_date
            if parsed_year and not pub_year:
                pub_year = parsed_year
        
        # External IDs
        external_ids = paper.get('externalIds', {}) or {}
        doi = normalize_doi(external_ids.get('DOI'))
        pmid = external_ids.get('PubMed')
        pmcid = external_ids.get('PubMedCentral')
        if pmcid and not pmcid.startswith('PMC'):
            pmcid = f"PMC{pmcid}"
        
        # Journal info
        journal_info = paper.get('journal', {}) or {}
        journal = journal_info.get('name') or paper.get('venue')
        issn = journal_info.get('issn')
        
        # Fields of study
        fields_of_study = paper.get('fieldsOfStudy', []) or []
        
        # Publication types
        pub_types = paper.get('publicationTypes', []) or []
        
        # Check if it's a preprint
        venue = (paper.get('venue') or '').lower()
        is_preprint = any(preprint in venue for preprint in PREPRINT_VENUES)
        
        # RCT detection
        is_rct, detection_method = self._detect_rct(title, abstract, pub_types)
        
        # URL
        url = f"https://www.semanticscholar.org/paper/{paper_id}"
        if paper.get('isOpenAccess') and paper.get('openAccessPdf', {}).get('url'):
            url = paper['openAccessPdf']['url']
        
        return RCTRecord(
            source_primary="SemanticScholar",
            sources_found_in=["SemanticScholar"],
            s2PaperId=paper_id,
            pmid=pmid,
            pmcid=pmcid,
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            issn=issn,
            publication_date=pub_date,
            publication_year=pub_year,
            abstract=abstract,
            fields_of_study=fields_of_study,
            url=url,
            is_preprint=is_preprint,
            rct_flag=is_rct,
            rct_detection_method=detection_method,
        )
    
    def _detect_rct(self, title: str, abstract: str, pub_types: List[str]) -> tuple[bool, str]:
        """Detect if paper is an RCT."""
        # Check publication types first
        rct_pub_types = ['JournalArticle', 'ClinicalTrial']
        if 'ClinicalTrial' in pub_types:
            return True, "Semantic Scholar publication type: ClinicalTrial"
        
        # Fall back to text detection
        return detect_rct_from_text(title, abstract)
