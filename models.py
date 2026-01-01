"""
Canonical data models for RCT records.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date


@dataclass
class RCTRecord:
    """Normalized record schema for RCT papers from any source."""
    
    # Source tracking
    source_primary: str = ""
    sources_found_in: List[str] = field(default_factory=list)
    
    # Identifiers
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    doi: Optional[str] = None
    s2PaperId: Optional[str] = None
    openalex_id: Optional[str] = None
    crossref_doi: Optional[str] = None
    scopus_id: Optional[str] = None
    wos_id: Optional[str] = None
    dimensions_id: Optional[str] = None
    
    # Core metadata
    title: str = ""
    authors: List[str] = field(default_factory=list)
    journal: Optional[str] = None
    issn: Optional[str] = None
    publication_date: Optional[str] = None
    publication_year: Optional[int] = None
    language: Optional[str] = None
    abstract: Optional[str] = None
    mesh_terms: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    fields_of_study: List[str] = field(default_factory=list)
    url: Optional[str] = None
    publisher: Optional[str] = None
    is_preprint: bool = False
    
    # RCT detection
    rct_flag: bool = False
    rct_detection_method: str = ""
    
    # Classification
    topic: str = "Other/Unclear"
    classification_reason: str = ""
    classification_inputs_used: List[str] = field(default_factory=list)
    
    # LLM Classification (populated when using LM Studio refinement)
    llm_topic: Optional[str] = None
    llm_reasoning: Optional[str] = None
    llm_confidence: Optional[float] = None
    final_topic: Optional[str] = None
    topic_source: str = "Rules"  # "Rules", "LLM", or "Rules (LLM low confidence)"
    
    # Quality tracking
    data_quality_notes: Optional[str] = None
    
    def get_dedup_key(self) -> str:
        """Generate a key for deduplication based on available identifiers."""
        if self.doi:
            return f"doi:{self.doi.lower()}"
        if self.pmid:
            return f"pmid:{self.pmid}"
        if self.pmcid:
            return f"pmcid:{self.pmcid}"
        # Fallback: normalized title + first author + year
        title_norm = ''.join(c.lower() for c in self.title if c.isalnum())[:100]
        author_norm = self.authors[0].split()[-1].lower() if self.authors else ""
        year = self.publication_year or ""
        return f"fuzzy:{title_norm}|{author_norm}|{year}"
    
    def merge_with(self, other: 'RCTRecord') -> 'RCTRecord':
        """Merge another record into this one, combining sources and filling gaps."""
        # Combine sources
        for src in other.sources_found_in:
            if src not in self.sources_found_in:
                self.sources_found_in.append(src)
        
        # Fill in missing identifiers
        if not self.pmid and other.pmid:
            self.pmid = other.pmid
        if not self.pmcid and other.pmcid:
            self.pmcid = other.pmcid
        if not self.doi and other.doi:
            self.doi = other.doi
        if not self.s2PaperId and other.s2PaperId:
            self.s2PaperId = other.s2PaperId
        if not self.openalex_id and other.openalex_id:
            self.openalex_id = other.openalex_id
        if not self.crossref_doi and other.crossref_doi:
            self.crossref_doi = other.crossref_doi
        if not self.scopus_id and other.scopus_id:
            self.scopus_id = other.scopus_id
        if not self.wos_id and other.wos_id:
            self.wos_id = other.wos_id
        if not self.dimensions_id and other.dimensions_id:
            self.dimensions_id = other.dimensions_id
        
        # Fill in missing metadata (prefer more complete data)
        if not self.abstract and other.abstract:
            self.abstract = other.abstract
        if not self.journal and other.journal:
            self.journal = other.journal
        if not self.issn and other.issn:
            self.issn = other.issn
        if not self.publisher and other.publisher:
            self.publisher = other.publisher
        if not self.url and other.url:
            self.url = other.url
        if not self.language and other.language:
            self.language = other.language
        
        # Merge list fields
        for term in other.mesh_terms:
            if term not in self.mesh_terms:
                self.mesh_terms.append(term)
        for kw in other.keywords:
            if kw not in self.keywords:
                self.keywords.append(kw)
        for fos in other.fields_of_study:
            if fos not in self.fields_of_study:
                self.fields_of_study.append(fos)
        
        return self
    
    def to_dict(self) -> dict:
        """Convert to dictionary for output."""
        return {
            'source_primary': self.source_primary,
            'sources_found_in': '; '.join(self.sources_found_in),
            'pmid': self.pmid,
            'pmcid': self.pmcid,
            'doi': self.doi,
            's2PaperId': self.s2PaperId,
            'openalex_id': self.openalex_id,
            'title': self.title,
            'authors': '; '.join(self.authors),
            'journal': self.journal,
            'issn': self.issn,
            'publication_date': self.publication_date,
            'publication_year': self.publication_year,
            'language': self.language,
            'abstract': self.abstract,
            'mesh_terms': '; '.join(self.mesh_terms) if self.mesh_terms else None,
            'keywords': '; '.join(self.keywords) if self.keywords else None,
            'fields_of_study': '; '.join(self.fields_of_study) if self.fields_of_study else None,
            'url': self.url,
            'publisher': self.publisher,
            'rct_flag': self.rct_flag,
            'rct_detection_method': self.rct_detection_method,
            'topic': self.topic,
            'classification_reason': self.classification_reason,
            'data_quality_notes': self.data_quality_notes,
        }
