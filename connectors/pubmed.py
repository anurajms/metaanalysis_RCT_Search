"""
PubMed/MEDLINE connector using NCBI E-utilities.
"""

import requests
import xml.etree.ElementTree as ET
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseConnector
from ..models import RCTRecord
from ..config import (
    PUBMED_ESEARCH_URL, 
    PUBMED_EFETCH_URL, 
    RATE_LIMITS
)
from ..utils import (
    RateLimiter, 
    get_pubmed_date_range, 
    parse_date, 
    normalize_doi,
    chunk_list,
    logger
)


class PubMedConnector(BaseConnector):
    """Connector for PubMed/MEDLINE via NCBI E-utilities."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        rate = RATE_LIMITS['pubmed_with_key'] if api_key else RATE_LIMITS['pubmed_without_key']
        self.rate_limiter = RateLimiter(rate)
        self.session = requests.Session()
        
    @property
    def source_name(self) -> str:
        return "PubMed"
    
    def _build_params(self, **kwargs) -> dict:
        """Build request parameters with API key if available."""
        params = dict(kwargs)
        if self.api_key:
            params['api_key'] = self.api_key
        return params
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ET.ParseError))
    )
    def _esearch(self, query: str, max_records: Optional[int] = None) -> List[str]:
        """Execute E-utilities esearch and return PMIDs."""
        self.rate_limiter.wait()
        
        params = self._build_params(
            db='pubmed',
            term=query,
            retmax=max_records or 10000,
            retmode='json',
            usehistory='n'
        )
        
        logger.debug(f"PubMed esearch query: {query}")
        response = self.session.get(PUBMED_ESEARCH_URL, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        result = data.get('esearchresult', {})
        
        if 'error' in result:
            logger.error(f"PubMed search error: {result['error']}")
            return []
        
        pmids = result.get('idlist', [])
        count = int(result.get('count', 0))
        
        logger.info(f"PubMed found {count} results, returning {len(pmids)}")
        return pmids
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def _efetch(self, pmids: List[str]) -> str:
        """Fetch article details in XML format."""
        self.rate_limiter.wait()
        
        params = self._build_params(
            db='pubmed',
            id=','.join(pmids),
            retmode='xml',
            rettype='abstract'
        )
        
        response = self.session.get(PUBMED_EFETCH_URL, params=params, timeout=60)
        response.raise_for_status()
        return response.text
    
    def search(
        self, 
        days: int, 
        query: Optional[str] = None,
        max_records: Optional[int] = None,
        include_preprints: bool = False
    ) -> List[str]:
        """Search PubMed for RCTs published in the last N days."""
        start_date, end_date = get_pubmed_date_range(days)
        
        # Build query with RCT publication type filter
        query_parts = [
            f'("{start_date}"[EDAT] : "{end_date}"[EDAT])',
            '"Randomized Controlled Trial"[pt]'
        ]
        
        if query:
            query_parts.append(f'({query})')
        
        # Exclude preprints by filtering for indexed records
        if not include_preprints:
            query_parts.append('medline[sb]')
        
        full_query = ' AND '.join(query_parts)
        
        return self._esearch(full_query, max_records)
    
    def fetch_details(self, ids: List[str]) -> List[RCTRecord]:
        """Fetch detailed records for PMIDs."""
        records = []
        
        # Process in chunks to avoid URL length limits
        for chunk in chunk_list(ids, 200):
            xml_text = self._efetch(chunk)
            chunk_records = self._parse_xml(xml_text)
            records.extend(chunk_records)
        
        return records
    
    def _parse_xml(self, xml_text: str) -> List[RCTRecord]:
        """Parse PubMed XML response into RCTRecords."""
        records = []
        
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.error(f"Failed to parse PubMed XML: {e}")
            return records
        
        for article in root.findall('.//PubmedArticle'):
            try:
                record = self._parse_article(article)
                if record:
                    records.append(record)
            except Exception as e:
                logger.warning(f"Failed to parse article: {e}")
                continue
        
        return records
    
    def _parse_article(self, article: ET.Element) -> Optional[RCTRecord]:
        """Parse a single PubMed article element."""
        medline = article.find('.//MedlineCitation')
        if medline is None:
            return None
        
        # PMID
        pmid_elem = medline.find('.//PMID')
        pmid = pmid_elem.text if pmid_elem is not None else None
        
        if not pmid:
            return None
        
        article_elem = medline.find('.//Article')
        if article_elem is None:
            return None
        
        # Title
        title_elem = article_elem.find('.//ArticleTitle')
        title = self._get_element_text(title_elem) or ""
        
        # Abstract
        abstract_parts = []
        for abstract_text in article_elem.findall('.//AbstractText'):
            label = abstract_text.get('Label', '')
            text = self._get_element_text(abstract_text) or ''
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract = ' '.join(abstract_parts) if abstract_parts else None
        
        # Authors
        authors = []
        for author in article_elem.findall('.//Author'):
            lastname = author.findtext('LastName', '')
            forename = author.findtext('ForeName', '')
            if lastname:
                full_name = f"{forename} {lastname}".strip() if forename else lastname
                authors.append(full_name)
        
        # Journal
        journal_elem = article_elem.find('.//Journal')
        journal = None
        issn = None
        if journal_elem is not None:
            journal = journal_elem.findtext('.//Title') or journal_elem.findtext('.//ISOAbbreviation')
            issn_elem = journal_elem.find('.//ISSN')
            issn = issn_elem.text if issn_elem is not None else None
        
        # Publication date
        pub_date = None
        pub_year = None
        
        # Try PubDate first
        pubdate_elem = article_elem.find('.//PubDate')
        if pubdate_elem is not None:
            year = pubdate_elem.findtext('Year')
            month = pubdate_elem.findtext('Month', '01')
            day = pubdate_elem.findtext('Day', '01')
            
            # Handle MedlineDate format
            medline_date = pubdate_elem.findtext('MedlineDate')
            if medline_date:
                pub_date, pub_year = parse_date(medline_date)
            elif year:
                pub_year = int(year)
                # Convert month name to number if necessary
                try:
                    month_num = int(month)
                except ValueError:
                    month_map = {
                        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                        'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                    }
                    month_num = month_map.get(month.lower()[:3], 1)
                
                try:
                    day_num = int(day)
                except ValueError:
                    day_num = 1
                    
                pub_date = f"{year}-{str(month_num).zfill(2)}-{str(day_num).zfill(2)}"
        
        # DOI and PMCID from ArticleIdList
        doi = None
        pmcid = None
        pubmed_data = article.find('.//PubmedData')
        if pubmed_data is not None:
            for article_id in pubmed_data.findall('.//ArticleId'):
                id_type = article_id.get('IdType', '')
                if id_type == 'doi':
                    doi = normalize_doi(article_id.text)
                elif id_type == 'pmc':
                    pmcid = article_id.text
        
        # Also check ELocationID for DOI
        if not doi:
            for eloc in article_elem.findall('.//ELocationID'):
                if eloc.get('EIdType') == 'doi':
                    doi = normalize_doi(eloc.text)
                    break
        
        # MeSH terms
        mesh_terms = []
        for mesh in medline.findall('.//MeshHeading'):
            descriptor = mesh.find('.//DescriptorName')
            if descriptor is not None and descriptor.text:
                mesh_terms.append(descriptor.text)
        
        # Keywords
        keywords = []
        for kw in medline.findall('.//Keyword'):
            if kw.text:
                keywords.append(kw.text)
        
        # Language
        language = article_elem.findtext('.//Language', 'eng')
        
        # Publication types (check for RCT)
        pub_types = []
        for pt in article_elem.findall('.//PublicationType'):
            if pt.text:
                pub_types.append(pt.text)
        
        is_rct = any('Randomized Controlled Trial' in pt for pt in pub_types)
        
        # URL
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        
        return RCTRecord(
            source_primary="PubMed",
            sources_found_in=["PubMed"],
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
            rct_flag=is_rct,
            rct_detection_method="PubMed publication type filter: Randomized Controlled Trial[pt]",
        )
    
    def _get_element_text(self, elem: Optional[ET.Element]) -> Optional[str]:
        """Get text content from an element, including nested elements."""
        if elem is None:
            return None
        
        # Get all text including from child elements
        text_parts = []
        if elem.text:
            text_parts.append(elem.text)
        for child in elem:
            if child.text:
                text_parts.append(child.text)
            if child.tail:
                text_parts.append(child.tail)
        
        return ''.join(text_parts).strip() if text_parts else None
