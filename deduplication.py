"""
Cross-source deduplication logic.
"""

from typing import List, Dict
from collections import defaultdict

from .models import RCTRecord
from .utils import normalize_doi, normalize_title, title_similarity, logger


def deduplicate_records(records: List[RCTRecord]) -> List[RCTRecord]:
    """
    Deduplicate records across sources using DOI, PMID/PMCID, and fuzzy matching.
    
    Priority order:
    1. DOI match (exact, case-insensitive)
    2. PMID or PMCID match
    3. Fuzzy match (title similarity + first author + year)
    
    When merging duplicates, combine sources and fill in missing metadata.
    
    Args:
        records: List of RCTRecord objects from various sources
        
    Returns:
        Deduplicated list of RCTRecord objects
    """
    if not records:
        return []
    
    # Build indices for fast lookup
    doi_index: Dict[str, RCTRecord] = {}
    pmid_index: Dict[str, RCTRecord] = {}
    pmcid_index: Dict[str, RCTRecord] = {}
    
    # Records that couldn't be matched by ID
    unmatched: List[RCTRecord] = []
    
    # Final deduplicated records
    deduplicated: Dict[str, RCTRecord] = {}
    
    merge_count = 0
    
    for record in records:
        matched = False
        matched_record = None
        match_key = None
        
        # Try DOI match first
        if record.doi:
            doi_key = normalize_doi(record.doi)
            if doi_key in doi_index:
                matched_record = doi_index[doi_key]
                match_key = f"doi:{doi_key}"
                matched = True
        
        # Try PMID match
        if not matched and record.pmid:
            pmid_key = record.pmid.strip()
            if pmid_key in pmid_index:
                matched_record = pmid_index[pmid_key]
                match_key = f"pmid:{pmid_key}"
                matched = True
        
        # Try PMCID match
        if not matched and record.pmcid:
            pmcid_key = record.pmcid.strip()
            if pmcid_key in pmcid_index:
                matched_record = pmcid_index[pmcid_key]
                match_key = f"pmcid:{pmcid_key}"
                matched = True
        
        if matched and matched_record:
            # Merge records
            matched_record.merge_with(record)
            merge_count += 1
            logger.debug(f"Merged record via {match_key}: {record.title[:50]}...")
        else:
            # Add to indices
            dedup_key = record.get_dedup_key()
            
            if record.doi:
                doi_key = normalize_doi(record.doi)
                doi_index[doi_key] = record
            if record.pmid:
                pmid_index[record.pmid.strip()] = record
            if record.pmcid:
                pmcid_index[record.pmcid.strip()] = record
            
            # Check for fuzzy match in unmatched
            fuzzy_match = None
            if dedup_key.startswith('fuzzy:'):
                fuzzy_match = _find_fuzzy_match(record, unmatched)
            
            if fuzzy_match:
                fuzzy_match.merge_with(record)
                merge_count += 1
                logger.debug(f"Merged via fuzzy match: {record.title[:50]}...")
            else:
                unmatched.append(record)
                deduplicated[dedup_key] = record
    
    logger.info(f"Deduplication: {len(records)} records -> {len(deduplicated)} unique ({merge_count} merges)")
    
    return list(deduplicated.values())


def _find_fuzzy_match(record: RCTRecord, candidates: List[RCTRecord]) -> RCTRecord:
    """
    Find a fuzzy match for a record in the candidate list.
    
    Matching criteria:
    - Title similarity > 0.9
    - Same first author last name (if available)
    - Same publication year (if available)
    """
    if not record.title:
        return None
    
    record_title_norm = normalize_title(record.title)
    record_author = _get_first_author_lastname(record.authors)
    record_year = record.publication_year
    
    for candidate in candidates:
        # Check year match if both have years
        if record_year and candidate.publication_year:
            if record_year != candidate.publication_year:
                continue
        
        # Check title similarity
        if not candidate.title:
            continue
        
        similarity = title_similarity(record.title, candidate.title)
        if similarity < 0.9:
            continue
        
        # Check author match if both have authors
        if record_author:
            candidate_author = _get_first_author_lastname(candidate.authors)
            if candidate_author and record_author.lower() != candidate_author.lower():
                continue
        
        # Match found
        return candidate
    
    return None


def _get_first_author_lastname(authors: List[str]) -> str:
    """Extract the last name of the first author."""
    if not authors:
        return ""
    
    first_author = authors[0].strip()
    if not first_author:
        return ""
    
    # Handle "LastName, FirstName" format
    if ',' in first_author:
        return first_author.split(',')[0].strip()
    
    # Handle "FirstName LastName" format
    parts = first_author.split()
    if parts:
        return parts[-1].strip()
    
    return first_author
