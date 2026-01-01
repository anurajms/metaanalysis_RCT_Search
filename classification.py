"""
Topic classification using rules-based approach for all medical specialties.
"""

import re
from typing import Tuple, List, Dict

from .config import MEDICAL_SPECIALTY_TERMS


def classify_topic(
    record,
    use_llm: bool = False
) -> Tuple[str, str, List[str]]:
    """
    Classify a record into a medical specialty.
    
    Supports 24 medical specialties including:
    - Cardiology, Gastroenterology, Oncology, Pulmonology
    - Neurology, Nephrology, Endocrinology, Rheumatology
    - Infectious Disease, Hematology, Psychiatry, Dermatology
    - Ophthalmology, Orthopedics, Urology, Obstetrics/Gynecology
    - Pediatrics, Geriatrics, Emergency Medicine, Anesthesiology
    - Radiology, Allergy/Immunology, Pain Medicine, Physical Medicine/Rehabilitation
    
    Args:
        record: RCTRecord object
        use_llm: Whether to use LLM classification (not implemented)
        
    Returns:
        Tuple of (topic, classification_reason, inputs_used)
    """
    inputs_used = []
    
    # Initialize scores and matches for all specialties
    scores: Dict[str, int] = {specialty: 0 for specialty in MEDICAL_SPECIALTY_TERMS}
    matches: Dict[str, List[str]] = {specialty: [] for specialty in MEDICAL_SPECIALTY_TERMS}
    
    # Check MeSH terms (highest priority - weight 3)
    if record.mesh_terms:
        inputs_used.append('MeSH terms')
        for term in record.mesh_terms:
            term_lower = term.lower()
            for specialty, terms in MEDICAL_SPECIALTY_TERMS.items():
                for specialty_term in terms:
                    if specialty_term in term_lower:
                        scores[specialty] += 3
                        if f"MeSH:{term}" not in matches[specialty]:
                            matches[specialty].append(f"MeSH:{term}")
                        break
    
    # Check fields of study (weight 2)
    if record.fields_of_study:
        inputs_used.append('fields_of_study')
        for field in record.fields_of_study:
            field_lower = field.lower()
            for specialty, terms in MEDICAL_SPECIALTY_TERMS.items():
                for specialty_term in terms:
                    if specialty_term in field_lower:
                        scores[specialty] += 2
                        if f"field:{field}" not in matches[specialty]:
                            matches[specialty].append(f"field:{field}")
                        break
    
    # Check keywords (weight 2)
    if record.keywords:
        inputs_used.append('keywords')
        for kw in record.keywords:
            kw_lower = kw.lower()
            for specialty, terms in MEDICAL_SPECIALTY_TERMS.items():
                for specialty_term in terms:
                    if specialty_term in kw_lower:
                        scores[specialty] += 2
                        if f"keyword:{kw}" not in matches[specialty]:
                            matches[specialty].append(f"keyword:{kw}")
                        break
    
    # Check title (weight 2)
    if record.title:
        inputs_used.append('title')
        title_lower = record.title.lower()
        title_words = set(re.findall(r'\b\w+\b', title_lower))
        
        for specialty, terms in MEDICAL_SPECIALTY_TERMS.items():
            for specialty_term in terms:
                if specialty_term in title_lower or specialty_term in title_words:
                    scores[specialty] += 2
                    if len(matches[specialty]) < 5:  # Limit matches stored
                        matches[specialty].append(f"title:{specialty_term}")
    
    # Check abstract (weight 1 per distinct term)
    if record.abstract:
        inputs_used.append('abstract')
        abstract_lower = record.abstract.lower()
        
        for specialty, terms in MEDICAL_SPECIALTY_TERMS.items():
            matches_in_abstract = set()
            for specialty_term in terms:
                if re.search(r'\b' + re.escape(specialty_term) + r'\b', abstract_lower):
                    matches_in_abstract.add(specialty_term)
            
            scores[specialty] += len(matches_in_abstract)
            if matches_in_abstract:
                matches[specialty].append(f"abstract:{len(matches_in_abstract)} terms")
    
    # Check journal name (weight 3)
    if record.journal:
        inputs_used.append('journal')
        journal_lower = record.journal.lower()
        
        # Journal-specific keywords for each specialty
        journal_keywords = {
            'Cardiology': ['cardio', 'heart', 'circulation', 'hypertension', 'stroke'],
            'Gastroenterology': ['gastro', 'hepat', 'digest', 'gut', 'bowel', 'liver'],
            'Oncology': ['cancer', 'oncol', 'tumor', 'neoplasm', 'leukemia', 'lymphoma'],
            'Pulmonology': ['pulmon', 'respir', 'lung', 'chest', 'thorax'],
            'Neurology': ['neuro', 'brain', 'epilep', 'alzheimer'],
            'Nephrology': ['nephro', 'kidney', 'renal', 'dialysis'],
            'Endocrinology': ['endocrin', 'diabet', 'thyroid', 'hormone', 'metabol'],
            'Rheumatology': ['rheumat', 'arthritis', 'lupus'],
            'Infectious Disease': ['infect', 'antimicrob', 'virus', 'hiv', 'aids'],
            'Hematology': ['hematol', 'blood', 'transfus', 'thromb'],
            'Psychiatry': ['psychiatr', 'psychol', 'mental health', 'depression'],
            'Dermatology': ['dermatol', 'skin', 'cutaneous'],
            'Ophthalmology': ['ophthalm', 'eye', 'vision', 'retina'],
            'Orthopedics': ['orthop', 'bone', 'joint', 'spine', 'musculoskel'],
            'Urology': ['urol', 'bladder', 'prostate'],
            'Obstetrics/Gynecology': ['obstet', 'gynec', 'fertil', 'reprod'],
            'Pediatrics': ['pediatr', 'paediatr', 'child', 'neonat'],
            'Geriatrics': ['geriatr', 'aging', 'gerontol'],
            'Emergency Medicine': ['emerg', 'trauma', 'critical care', 'intensive care'],
            'Anesthesiology': ['anesthes', 'anaesthes', 'pain'],
            'Radiology': ['radiol', 'imaging'],
            'Allergy/Immunology': ['allerg', 'immunol'],
            'Pain Medicine': ['pain'],
            'Physical Medicine/Rehabilitation': ['rehabil', 'physiatr', 'physical med'],
        }
        
        for specialty, keywords in journal_keywords.items():
            for keyword in keywords:
                if keyword in journal_lower:
                    scores[specialty] += 3
                    matches[specialty].append(f"journal:{record.journal}")
                    break
    
    # Determine classification - find highest scoring specialty
    max_score = max(scores.values())
    min_score_threshold = 3
    margin = 2
    
    if max_score >= min_score_threshold:
        # Get all specialties with max score
        top_specialties = [s for s, score in scores.items() if score == max_score]
        
        if len(top_specialties) == 1:
            # Clear winner
            topic = top_specialties[0]
            matched = matches[topic][:5]  # Limit to 5 examples
            
            # Get second highest score for comparison
            sorted_scores = sorted(scores.values(), reverse=True)
            second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0
            
            reason = f"Score {max_score} vs next {second_score}. Matches: {', '.join(matched)}"
        else:
            # Tie between multiple specialties
            topic = top_specialties[0]  # Take first alphabetically
            matched = matches[topic][:3]
            reason = f"Tied at {max_score} with {', '.join(top_specialties[:3])}. Using: {topic}"
    else:
        topic = 'Other/Unclear'
        if max_score == 0:
            reason = "No matching terms found in any field"
        else:
            # Show top 3 scores
            top_3 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
            scores_str = ', '.join([f"{s}:{sc}" for s, sc in top_3 if sc > 0])
            reason = f"Below threshold. Top scores: {scores_str}" if scores_str else "Minimal matches"
    
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
