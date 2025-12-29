"""
RCT detection logic using text-based signals.
"""

import re
from typing import Tuple


# Strong RCT signals - presence of any one is strong evidence
STRONG_RCT_PATTERNS = [
    r'\brandomized\s+controlled\s+trial\b',
    r'\brandomised\s+controlled\s+trial\b',
    r'\brandomized\s+clinical\s+trial\b',
    r'\brandomised\s+clinical\s+trial\b',
    r'\bplacebo[- ]controlled\s+(?:trial|study)\b',
    r'\bdouble[- ]blind(?:ed)?\s+(?:randomized|randomised)\b',
    r'\brandomized[- ]controlled\b',
    r'\brandomised[- ]controlled\b',
]

# Moderate RCT signals - need multiple
MODERATE_RCT_PATTERNS = [
    r'\brandomized\b',
    r'\brandomised\b',
    r'\brandomization\b',
    r'\brandomisation\b',
    r'\bplacebo\b',
    r'\bdouble[- ]blind(?:ed)?\b',
    r'\bsingle[- ]blind(?:ed)?\b',
    r'\btriple[- ]blind(?:ed)?\b',
    r'\bcontrolled\s+trial\b',
    r'\bclinical\s+trial\b',
    r'\brandom\s+(?:allocation|assignment)\b',
    r'\bintention[- ]to[- ]treat\b',
    r'\bintent[- ]to[- ]treat\b',
    r'\bITT\s+(?:analysis|population)\b',
    r'\bper[- ]protocol\b',
    r'\bconsort\b',
]

# Weak signals - supplementary
WEAK_RCT_PATTERNS = [
    r'\barm(?:s)?\b.*\b(?:intervention|treatment|control)\b',
    r'\b(?:intervention|treatment)\s+(?:group|arm)\b',
    r'\bcontrol\s+(?:group|arm)\b',
    r'\bprimary\s+(?:endpoint|outcome)\b',
    r'\bsecondary\s+(?:endpoint|outcome)\b',
    r'\benrollment\b',
    r'\benrolment\b',
    r'\bwash[- ]?out\b',
    r'\bcrossover\b',
    r'\bcross[- ]over\b',
    r'\bparallel[- ]group\b',
]

# Negative signals - suggest it's NOT an RCT
NEGATIVE_PATTERNS = [
    r'\bretrospective\b',
    r'\bobservational\s+study\b',
    r'\bcohort\s+study\b',
    r'\bcase[- ]control\b',
    r'\bcross[- ]sectional\b',
    r'\bmeta[- ]analysis\b',
    r'\bsystematic\s+review\b',
    r'\bcase\s+report\b',
    r'\bcase\s+series\b',
    r'\breview\s+article\b',
    r'\beditorial\b',
    r'\bcommentary\b',
    r'\bletter\s+to\b',
    r'\bprotocol\s+(?:for|of)\b',
    r'\bstudy\s+protocol\b',
]


def detect_rct_from_text(
    title: str, 
    abstract: str,
    keywords: list = None
) -> Tuple[bool, str]:
    """
    Detect if a paper is an RCT based on text signals.
    
    Returns:
        Tuple of (is_rct, detection_method)
    """
    if not title and not abstract:
        return False, "No title or abstract available"
    
    # Combine text for analysis
    text = f"{title or ''} {abstract or ''}"
    if keywords:
        text += ' ' + ' '.join(keywords)
    
    text = text.lower()
    
    # Check for negative signals first
    negative_count = 0
    negative_matches = []
    for pattern in NEGATIVE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            negative_count += 1
            negative_matches.append(pattern)
    
    # If strong negative signals and no strong positive signals, likely not RCT
    if negative_count >= 2:
        # Still check for explicit RCT in title (might be RCT comparing to meta-analysis, etc.)
        if not re.search(r'\brandomized\s+controlled\s+trial\b', title.lower()) and \
           not re.search(r'\brandomised\s+controlled\s+trial\b', title.lower()):
            return False, f"Negative signals detected: {', '.join(negative_matches[:3])}"
    
    # Check for strong RCT signals
    for pattern in STRONG_RCT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            location = "title" if re.search(pattern, (title or '').lower(), re.IGNORECASE) else "abstract"
            return True, f"Strong RCT signal in {location}: '{match.group()}'"
    
    # Check for moderate signals
    moderate_matches = []
    for pattern in MODERATE_RCT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            moderate_matches.append(pattern.replace(r'\b', '').replace('(?:', '').replace(')', ''))
    
    # Need at least 2 moderate signals
    if len(moderate_matches) >= 2:
        signals = moderate_matches[:3]
        return True, f"Multiple RCT signals detected: {', '.join(signals)}"
    
    # Check for one moderate + weak signals
    if len(moderate_matches) >= 1:
        weak_matches = []
        for pattern in WEAK_RCT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                weak_matches.append(pattern.replace(r'\b', ''))
        
        if len(weak_matches) >= 2:
            return True, f"RCT signal ({moderate_matches[0]}) with supporting evidence"
    
    return False, "No sufficient RCT signals detected"


def is_rct_publication_type(pub_types: list) -> Tuple[bool, str]:
    """
    Check if publication types indicate RCT.
    
    Args:
        pub_types: List of publication type strings
        
    Returns:
        Tuple of (is_rct, detection_method)
    """
    if not pub_types:
        return False, ""
    
    rct_types = [
        'randomized controlled trial',
        'randomised controlled trial',
        'controlled clinical trial',
        'clinical trial',
        'rct',
    ]
    
    for pt in pub_types:
        pt_lower = pt.lower()
        for rct_type in rct_types:
            if rct_type in pt_lower:
                return True, f"Publication type: {pt}"
    
    return False, ""
