"""
Topic classification using rules-based approach for all medical specialties.
Uses word-boundary matching to avoid false positives.
"""

import re
from typing import Tuple, List, Dict, Set

from .config import MEDICAL_SPECIALTY_TERMS


# Terms that should ONLY match as whole words (not substrings)
# This prevents "pulsed" matching "ed" (Emergency Department)
WHOLE_WORD_TERMS = {
    'ed', 'ms', 'rct', 'ibd', 'gerd', 'copd', 'tb', 'hiv', 'aids', 'icu',
    'cpr', 'dvt', 'tia', 'osa', 'eeg', 'csf', 'gfr', 'aki', 'ckd', 'pkd',
    'sle', 'mds', 'ocd', 'ptsd', 'cbt', 'adhd', 'amd', 'iop', 'acl', 'bph',
    'psa', 'ivf', 'nicu', 'ards', 'cad', 'mi', 'chf', 'afib', 'pe', 'gi',
    'uti', 'sti', 'std', 'mrsa', 'ipf', 'fev1', 'fvc', 'als', 'pmr',
}

# MeSH terms to IGNORE (they don't indicate specialty)
IGNORED_MESH_TERMS = {
    'middle aged', 'adult', 'aged', 'young adult', 'female', 'male',
    'humans', 'treatment outcome', 'prospective studies', 'retrospective studies',
    'follow-up studies', 'double-blind method', 'single-blind method',
    'randomized controlled trial', 'randomized controlled trials as topic',
    'time factors', 'reference values', 'methods', 'standards',
    'education', 'education, nursing', 'education, nursing, continuing',
    'education, medical', 'education, medical, continuing',
    'teaching', 'learning', 'curriculum',
}


def _is_word_match(term: str, text: str) -> bool:
    """
    Check if term appears in text as a whole word (not substring).
    For short terms or acronyms, require word boundaries.
    """
    term_lower = term.lower()
    text_lower = text.lower()
    
    # For very short terms or known acronyms, require word boundary
    if len(term) <= 3 or term_lower in WHOLE_WORD_TERMS:
        pattern = r'\b' + re.escape(term_lower) + r'\b'
        return bool(re.search(pattern, text_lower))
    
    # For longer terms, substring match is acceptable
    return term_lower in text_lower


def _should_ignore_mesh(mesh_term: str) -> bool:
    """Check if a MeSH term should be ignored for classification."""
    mesh_lower = mesh_term.lower()
    for ignored in IGNORED_MESH_TERMS:
        if ignored in mesh_lower:
            return True
    return False


def classify_topic(
    record,
    use_llm: bool = False
) -> Tuple[str, str, List[str]]:
    """
    Classify a record into a medical specialty.
    
    Uses careful word-boundary matching to avoid false positives.
    
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
            # Skip non-informative MeSH terms
            if _should_ignore_mesh(term):
                continue
                
            term_lower = term.lower()
            for specialty, terms in MEDICAL_SPECIALTY_TERMS.items():
                for specialty_term in terms:
                    if _is_word_match(specialty_term, term_lower):
                        scores[specialty] += 3
                        match_str = f"MeSH:{term}"
                        if match_str not in matches[specialty]:
                            matches[specialty].append(match_str)
                        break
    
    # Check fields of study (weight 2)
    if record.fields_of_study:
        inputs_used.append('fields_of_study')
        for field in record.fields_of_study:
            for specialty, terms in MEDICAL_SPECIALTY_TERMS.items():
                for specialty_term in terms:
                    if _is_word_match(specialty_term, field):
                        scores[specialty] += 2
                        match_str = f"field:{field}"
                        if match_str not in matches[specialty]:
                            matches[specialty].append(match_str)
                        break
    
    # Check keywords (weight 2)
    if record.keywords:
        inputs_used.append('keywords')
        for kw in record.keywords:
            for specialty, terms in MEDICAL_SPECIALTY_TERMS.items():
                for specialty_term in terms:
                    if _is_word_match(specialty_term, kw):
                        scores[specialty] += 2
                        match_str = f"keyword:{kw}"
                        if match_str not in matches[specialty]:
                            matches[specialty].append(match_str)
                        break
    
    # Check title (weight 2) - use word boundary matching
    if record.title:
        inputs_used.append('title')
        title_lower = record.title.lower()
        
        for specialty, terms in MEDICAL_SPECIALTY_TERMS.items():
            for specialty_term in terms:
                if _is_word_match(specialty_term, title_lower):
                    scores[specialty] += 2
                    if len(matches[specialty]) < 5:
                        matches[specialty].append(f"title:{specialty_term}")
    
    # Check abstract (weight 1 per distinct term)
    if record.abstract:
        inputs_used.append('abstract')
        abstract_lower = record.abstract.lower()
        
        for specialty, terms in MEDICAL_SPECIALTY_TERMS.items():
            matches_in_abstract = set()
            for specialty_term in terms:
                if _is_word_match(specialty_term, abstract_lower):
                    matches_in_abstract.add(specialty_term)
            
            scores[specialty] += len(matches_in_abstract)
            if matches_in_abstract:
                matches[specialty].append(f"abstract:{len(matches_in_abstract)} terms")
    
    # Check journal name (weight 4 - journal is strong indicator)
    if record.journal:
        inputs_used.append('journal')
        journal_lower = record.journal.lower()
        
        # Journal-specific keywords (more stringent matching)
        journal_keywords = {
            'Cardiology': ['cardiol', 'heart', 'circulation', 'hypertens', 'stroke', 'arrhythmia'],
            'Gastroenterology': ['gastroenter', 'hepatol', 'digest', 'gut', 'bowel', 'liver'],
            'Oncology': ['cancer', 'oncol', 'tumor', 'neoplasm', 'leukemia', 'lymphoma', 'carcinoma'],
            'Pulmonology': ['pulmon', 'respir', 'lung', 'chest', 'thorac'],
            'Neurology': ['neurol', 'brain', 'epilep', 'alzheimer', 'parkinson', 'cereb'],
            'Nephrology': ['nephrol', 'kidney', 'renal', 'dialysis'],
            'Endocrinology': ['endocrin', 'diabet', 'thyroid', 'hormone', 'metabol'],
            'Rheumatology': ['rheumat', 'arthritis', 'lupus'],
            'Infectious Disease': ['infect', 'antimicrob', 'virol', 'hiv', 'aids', 'tropical'],
            'Hematology': ['hematol', 'haematol', 'blood', 'transfus', 'thromb', 'coagul'],
            'Psychiatry': ['psychiatr', 'psychol', 'mental', 'depress', 'schizo'],
            'Dermatology': ['dermatol', 'skin', 'cutaneous'],
            'Ophthalmology': ['ophthalm', 'eye', 'vision', 'retina', 'ocular'],
            'Orthopedics': ['orthop', 'bone joint', 'spine', 'musculoskel', 'arthroplast'],
            'Urology': ['urol', 'bladder', 'prostat'],
            'Obstetrics/Gynecology': ['obstet', 'gynec', 'fertil', 'reprod', 'perinat', 'matern'],
            'Pediatrics': ['pediatr', 'paediatr', 'child', 'neonat', 'infant'],
            'Geriatrics': ['geriatr', 'aging', 'gerontol', 'elder'],
            'Emergency Medicine': ['emerg med', 'trauma', 'critical care', 'intensive care', 'accident'],
            'Anesthesiology': ['anesthes', 'anaesthes', 'anesth'],
            'Radiology': ['radiol', 'imaging', 'roentgen'],
            'Allergy/Immunology': ['allerg', 'immunol'],
            'Pain Medicine': ['pain med', 'pain manage'],
            'Physical Medicine/Rehabilitation': ['rehabil', 'physiatr', 'physical med', 'phys ther'],
        }
        
        for specialty, keywords in journal_keywords.items():
            for keyword in keywords:
                if keyword in journal_lower:
                    scores[specialty] += 4
                    matches[specialty].append(f"journal:{record.journal}")
                    break
    
    # Determine classification - find highest scoring specialty
    max_score = max(scores.values())
    min_score_threshold = 4  # Increased threshold for better accuracy
    margin = 2
    
    if max_score >= min_score_threshold:
        # Get all specialties with max score
        top_specialties = [s for s, score in scores.items() if score == max_score]
        
        if len(top_specialties) == 1:
            # Clear winner
            topic = top_specialties[0]
            matched = matches[topic][:5]
            
            # Get second highest score for comparison
            sorted_scores = sorted(scores.values(), reverse=True)
            second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0
            
            reason = f"Score {max_score} vs next {second_score}. Matches: {', '.join(matched)}"
        else:
            # Tie between multiple specialties - pick alphabetically first
            # But prefer more "specific" specialties over general ones
            specific_order = ['Oncology', 'Cardiology', 'Neurology', 'Gastroenterology', 
                            'Nephrology', 'Pulmonology', 'Endocrinology', 'Rheumatology',
                            'Infectious Disease', 'Hematology', 'Dermatology', 'Ophthalmology',
                            'Orthopedics', 'Urology', 'Obstetrics/Gynecology', 'Psychiatry',
                            'Pediatrics', 'Geriatrics', 'Anesthesiology', 'Radiology',
                            'Allergy/Immunology', 'Pain Medicine', 'Physical Medicine/Rehabilitation',
                            'Emergency Medicine']  # EM last as it's often over-matched
            
            topic = None
            for spec in specific_order:
                if spec in top_specialties:
                    topic = spec
                    break
            if topic is None:
                topic = top_specialties[0]
            
            matched = matches[topic][:3]
            other_tied = [s for s in top_specialties if s != topic][:2]
            reason = f"Score {max_score} (tied with {', '.join(other_tied)}). Matches: {', '.join(matched)}"
    else:
        topic = 'Other/Unclear'
        if max_score == 0:
            reason = "No matching terms found in any field"
        else:
            # Show top 3 scores
            top_3 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
            scores_str = ', '.join([f"{s}:{sc}" for s, sc in top_3 if sc > 0])
            reason = f"Below threshold ({max_score}<{min_score_threshold}). Top: {scores_str}" if scores_str else "Minimal matches"
    
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
