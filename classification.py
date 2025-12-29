"""
Topic classification using rules-based approach.
"""

import re
from typing import Tuple, List

from .config import CARDIOLOGY_TERMS, GASTROENTEROLOGY_TERMS


def classify_topic(
    record,
    use_llm: bool = False
) -> Tuple[str, str, List[str]]:
    """
    Classify a record into Cardiology, Gastroenterology, or Other/Unclear.
    
    Args:
        record: RCTRecord object
        use_llm: Whether to use LLM classification (not implemented)
        
    Returns:
        Tuple of (topic, classification_reason, inputs_used)
    """
    inputs_used = []
    scores = {
        'Cardiology': 0,
        'Gastroenterology': 0,
    }
    matches = {
        'Cardiology': [],
        'Gastroenterology': [],
    }
    
    # Check MeSH terms (highest priority)
    if record.mesh_terms:
        inputs_used.append('MeSH terms')
        for term in record.mesh_terms:
            term_lower = term.lower()
            for cardio_term in CARDIOLOGY_TERMS:
                if cardio_term in term_lower:
                    scores['Cardiology'] += 3
                    matches['Cardiology'].append(f"MeSH:{term}")
                    break
            for gastro_term in GASTROENTEROLOGY_TERMS:
                if gastro_term in term_lower:
                    scores['Gastroenterology'] += 3
                    matches['Gastroenterology'].append(f"MeSH:{term}")
                    break
    
    # Check fields of study
    if record.fields_of_study:
        inputs_used.append('fields_of_study')
        for field in record.fields_of_study:
            field_lower = field.lower()
            for cardio_term in CARDIOLOGY_TERMS:
                if cardio_term in field_lower:
                    scores['Cardiology'] += 2
                    matches['Cardiology'].append(f"field:{field}")
                    break
            for gastro_term in GASTROENTEROLOGY_TERMS:
                if gastro_term in field_lower:
                    scores['Gastroenterology'] += 2
                    matches['Gastroenterology'].append(f"field:{field}")
                    break
    
    # Check keywords
    if record.keywords:
        inputs_used.append('keywords')
        for kw in record.keywords:
            kw_lower = kw.lower()
            for cardio_term in CARDIOLOGY_TERMS:
                if cardio_term in kw_lower:
                    scores['Cardiology'] += 2
                    matches['Cardiology'].append(f"keyword:{kw}")
                    break
            for gastro_term in GASTROENTEROLOGY_TERMS:
                if gastro_term in kw_lower:
                    scores['Gastroenterology'] += 2
                    matches['Gastroenterology'].append(f"keyword:{kw}")
                    break
    
    # Check title (moderate weight)
    if record.title:
        inputs_used.append('title')
        title_lower = record.title.lower()
        title_words = set(re.findall(r'\b\w+\b', title_lower))
        
        for cardio_term in CARDIOLOGY_TERMS:
            if cardio_term in title_lower or cardio_term in title_words:
                scores['Cardiology'] += 2
                matches['Cardiology'].append(f"title:{cardio_term}")
        
        for gastro_term in GASTROENTEROLOGY_TERMS:
            if gastro_term in title_lower or gastro_term in title_words:
                scores['Gastroenterology'] += 2
                matches['Gastroenterology'].append(f"title:{gastro_term}")
    
    # Check abstract (lower weight, more text = more matches)
    if record.abstract:
        inputs_used.append('abstract')
        abstract_lower = record.abstract.lower()
        
        # Count distinct matches, not total occurrences
        cardio_matches_in_abstract = set()
        gastro_matches_in_abstract = set()
        
        for cardio_term in CARDIOLOGY_TERMS:
            if re.search(r'\b' + re.escape(cardio_term) + r'\b', abstract_lower):
                cardio_matches_in_abstract.add(cardio_term)
        
        for gastro_term in GASTROENTEROLOGY_TERMS:
            if re.search(r'\b' + re.escape(gastro_term) + r'\b', abstract_lower):
                gastro_matches_in_abstract.add(gastro_term)
        
        scores['Cardiology'] += len(cardio_matches_in_abstract)
        scores['Gastroenterology'] += len(gastro_matches_in_abstract)
        
        if cardio_matches_in_abstract:
            matches['Cardiology'].append(f"abstract:{len(cardio_matches_in_abstract)} terms")
        if gastro_matches_in_abstract:
            matches['Gastroenterology'].append(f"abstract:{len(gastro_matches_in_abstract)} terms")
    
    # Check journal name
    if record.journal:
        inputs_used.append('journal')
        journal_lower = record.journal.lower()
        
        cardio_journal_terms = ['cardio', 'heart', 'circulation', 'hypertension', 'stroke']
        gastro_journal_terms = ['gastro', 'hepat', 'digest', 'gut', 'bowel', 'liver']
        
        for term in cardio_journal_terms:
            if term in journal_lower:
                scores['Cardiology'] += 3
                matches['Cardiology'].append(f"journal:{record.journal}")
                break
        
        for term in gastro_journal_terms:
            if term in journal_lower:
                scores['Gastroenterology'] += 3
                matches['Gastroenterology'].append(f"journal:{record.journal}")
                break
    
    # Determine classification
    cardio_score = scores['Cardiology']
    gastro_score = scores['Gastroenterology']
    
    # Require minimum score and clear winner
    min_score = 3
    margin = 2
    
    if cardio_score >= min_score and cardio_score > gastro_score + margin:
        topic = 'Cardiology'
        matched = matches['Cardiology'][:5]  # Limit to 5 examples
        reason = f"Score {cardio_score} vs {gastro_score}. Matches: {', '.join(matched)}"
    elif gastro_score >= min_score and gastro_score > cardio_score + margin:
        topic = 'Gastroenterology'
        matched = matches['Gastroenterology'][:5]
        reason = f"Score {gastro_score} vs {cardio_score}. Matches: {', '.join(matched)}"
    else:
        topic = 'Other/Unclear'
        if cardio_score == 0 and gastro_score == 0:
            reason = "No matching terms found in any field"
        else:
            reason = f"Inconclusive. Cardiology:{cardio_score}, Gastroenterology:{gastro_score}"
    
    return topic, reason, inputs_used


def classify_records(records: list, use_llm: bool = False) -> list:
    """
    Classify all records and update their topic fields.
    
    Args:
        records: List of RCTRecord objects
        use_llm: Whether to use LLM classification
        
    Returns:
        The same list with updated classification fields
    """
    for record in records:
        topic, reason, inputs_used = classify_topic(record, use_llm)
        record.topic = topic
        record.classification_reason = reason
        record.classification_inputs_used = inputs_used
    
    return records
