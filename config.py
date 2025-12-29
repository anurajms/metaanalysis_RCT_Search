"""
Configuration constants and defaults.
"""

import os
from typing import Optional

# Default settings
DEFAULT_DAYS = 30
DEFAULT_OUTPUT = "rct_results.xlsx"

# API endpoints
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1"

EUROPEPMC_API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

CROSSREF_API_URL = "https://api.crossref.org/works"

OPENALEX_API_URL = "https://api.openalex.org/works"

# Enterprise APIs (optional)
SCOPUS_API_URL = "https://api.elsevier.com/content/search/scopus"
WOS_API_URL = "https://api.clarivate.com/api/wos"
DIMENSIONS_API_URL = "https://app.dimensions.ai/api"

# Rate limits (requests per second)
RATE_LIMITS = {
    'pubmed_with_key': 10,
    'pubmed_without_key': 3,
    'semantic_scholar': 10,  # 100 for partners, but 10 is safe default
    'europepmc': 10,
    'crossref': 50,  # polite pool
    'openalex': 10,
    'scopus': 5,
    'wos': 5,
    'dimensions': 5,
}

# RCT detection keywords
RCT_KEYWORDS = [
    'randomized controlled trial',
    'randomised controlled trial',
    'randomized clinical trial',
    'randomised clinical trial',
    'randomized trial',
    'randomised trial',
    'rct',
    'placebo-controlled',
    'placebo controlled',
    'double-blind',
    'double blind',
    'single-blind',
    'single blind',
    'triple-blind',
    'triple blind',
    'controlled trial',
    'random allocation',
    'random assignment',
]

# Publication types to exclude (for preprint filtering)
PREPRINT_VENUES = [
    'medrxiv',
    'biorxiv',
    'arxiv',
    'ssrn',
    'preprints',
    'research square',
    'authorea',
]

# Topic classification terms
CARDIOLOGY_TERMS = {
    'cardiology', 'cardiovascular', 'cardiac', 'heart', 'coronary', 
    'arrhythmia', 'atrial', 'ventricular', 'hypertension', 'myocardial',
    'infarction', 'angina', 'stroke', 'thrombosis', 'anticoagulant',
    'statin', 'lipid', 'cholesterol', 'atherosclerosis', 'heart failure',
    'cardiomyopathy', 'pacemaker', 'defibrillator', 'echocardiography',
    'angioplasty', 'bypass', 'valve', 'aortic', 'mitral', 'pulmonary embolism',
    'deep vein thrombosis', 'dvt', 'afib', 'atrial fibrillation',
    'blood pressure', 'antihypertensive', 'beta blocker', 'ace inhibitor',
    'calcium channel', 'diuretic', 'warfarin', 'heparin', 'aspirin',
}

GASTROENTEROLOGY_TERMS = {
    'gastroenterology', 'gastrointestinal', 'digestive', 'gi tract',
    'intestinal', 'intestine', 'colon', 'colonic', 'colorectal',
    'hepatology', 'hepatic', 'liver', 'cirrhosis', 'hepatitis',
    'esophageal', 'esophagus', 'stomach', 'gastric', 'peptic',
    'bowel', 'ibd', 'crohn', 'colitis', 'ulcerative colitis',
    'gerd', 'reflux', 'pancreatic', 'pancreas', 'pancreatitis',
    'gallbladder', 'biliary', 'cholecystitis', 'cholelithiasis',
    'endoscopy', 'colonoscopy', 'gastroscopy', 'ercp',
    'celiac', 'gluten', 'microbiome', 'probiotic', 'constipation',
    'diarrhea', 'dyspepsia', 'h pylori', 'helicobacter',
    'barrett', 'adenocarcinoma', 'polyp', 'diverticulitis',
}


def get_api_key(key_name: str, cli_value: Optional[str] = None) -> Optional[str]:
    """Get API key from CLI argument or environment variable."""
    if cli_value:
        return cli_value
    
    env_mapping = {
        'ncbi': 'NCBI_API_KEY',
        'semantic_scholar': 'SEMANTIC_SCHOLAR_API_KEY',
        'scopus': 'SCOPUS_API_KEY',
        'wos': 'WOS_API_KEY',
        'dimensions': 'DIMENSIONS_API_KEY',
    }
    
    env_var = env_mapping.get(key_name)
    if env_var:
        return os.environ.get(env_var)
    return None
