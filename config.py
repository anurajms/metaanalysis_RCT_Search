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

# =============================================================================
# MEDICAL SPECIALTY CLASSIFICATION TERMS
# =============================================================================

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

ONCOLOGY_TERMS = {
    'oncology', 'cancer', 'carcinoma', 'tumor', 'tumour', 'neoplasm',
    'malignant', 'malignancy', 'metastatic', 'metastasis', 'chemotherapy',
    'radiation therapy', 'radiotherapy', 'immunotherapy', 'targeted therapy',
    'checkpoint inhibitor', 'pd-1', 'pd-l1', 'ctla-4', 'car-t',
    'leukemia', 'leukaemia', 'lymphoma', 'myeloma', 'sarcoma', 'melanoma',
    'breast cancer', 'lung cancer', 'prostate cancer', 'colorectal cancer',
    'ovarian cancer', 'cervical cancer', 'pancreatic cancer', 'gastric cancer',
    'hepatocellular', 'renal cell', 'bladder cancer', 'thyroid cancer',
    'glioblastoma', 'brain tumor', 'head and neck cancer', 'esophageal cancer',
    'biopsy', 'staging', 'tnm', 'oncologist', 'tumor marker',
    'survival', 'progression-free', 'response rate', 'remission',
}

PULMONOLOGY_TERMS = {
    'pulmonology', 'pulmonary', 'respiratory', 'lung', 'bronchial',
    'asthma', 'copd', 'chronic obstructive', 'emphysema', 'bronchitis',
    'pneumonia', 'tuberculosis', 'tb', 'pleural', 'pleurisy',
    'interstitial lung', 'pulmonary fibrosis', 'ipf', 'sarcoidosis',
    'bronchiectasis', 'cystic fibrosis', 'pulmonary hypertension',
    'sleep apnea', 'osa', 'cpap', 'ventilation', 'ventilator',
    'spirometry', 'fev1', 'fvc', 'bronchoscopy', 'thoracoscopy',
    'oxygen therapy', 'inhaler', 'bronchodilator', 'corticosteroid',
    'ards', 'acute respiratory', 'dyspnea', 'wheezing',
}

NEUROLOGY_TERMS = {
    'neurology', 'neurological', 'brain', 'cerebral', 'neural',
    'alzheimer', 'dementia', 'parkinson', 'parkinsonian', 'epilepsy',
    'seizure', 'multiple sclerosis', 'ms', 'migraine', 'headache',
    'neuropathy', 'neuropathic', 'peripheral nerve', 'myasthenia',
    'als', 'amyotrophic', 'huntington', 'dystonia', 'tremor',
    'stroke', 'ischemic stroke', 'hemorrhagic stroke', 'tia',
    'meningitis', 'encephalitis', 'guillain-barre', 'mri brain',
    'eeg', 'electroencephalogram', 'lumbar puncture', 'csf',
    'dopamine', 'serotonin', 'acetylcholine', 'neurotransmitter',
}

NEPHROLOGY_TERMS = {
    'nephrology', 'renal', 'kidney', 'glomerular', 'glomerulonephritis',
    'chronic kidney disease', 'ckd', 'acute kidney injury', 'aki',
    'dialysis', 'hemodialysis', 'peritoneal dialysis', 'kidney transplant',
    'proteinuria', 'albuminuria', 'hematuria', 'creatinine', 'gfr',
    'nephrotic syndrome', 'nephritic', 'polycystic kidney', 'pkd',
    'uremia', 'electrolyte', 'sodium', 'potassium', 'phosphorus',
    'hyperkalemia', 'hyponatremia', 'acidosis', 'alkalosis',
}

ENDOCRINOLOGY_TERMS = {
    'endocrinology', 'endocrine', 'hormone', 'hormonal', 'diabetes',
    'diabetic', 'insulin', 'glucose', 'glycemic', 'hba1c', 'a1c',
    'thyroid', 'hypothyroidism', 'hyperthyroidism', 'graves', 'hashimoto',
    'adrenal', 'cushing', 'addison', 'cortisol', 'aldosterone',
    'pituitary', 'growth hormone', 'prolactin', 'acromegaly',
    'parathyroid', 'calcium', 'osteoporosis', 'bone density',
    'testosterone', 'estrogen', 'menopause', 'pcos', 'polycystic ovary',
    'type 1 diabetes', 'type 2 diabetes', 'metabolic syndrome', 'obesity',
}

RHEUMATOLOGY_TERMS = {
    'rheumatology', 'rheumatic', 'arthritis', 'rheumatoid', 'osteoarthritis',
    'lupus', 'sle', 'systemic lupus', 'sjogren', 'scleroderma',
    'vasculitis', 'gout', 'pseudogout', 'ankylosing spondylitis',
    'psoriatic arthritis', 'fibromyalgia', 'polymyalgia', 'myositis',
    'dermatomyositis', 'polymyositis', 'joint pain', 'synovitis',
    'autoimmune', 'biologic', 'dmard', 'methotrexate', 'tnf inhibitor',
    'anti-inflammatory', 'nsaid', 'corticosteroid',
}

INFECTIOUS_DISEASE_TERMS = {
    'infectious disease', 'infection', 'bacterial', 'viral', 'fungal',
    'antibiotic', 'antimicrobial', 'antiviral', 'antifungal',
    'sepsis', 'septic', 'bacteremia', 'hiv', 'aids', 'antiretroviral',
    'hepatitis b', 'hepatitis c', 'hbv', 'hcv', 'influenza', 'covid',
    'coronavirus', 'sars-cov-2', 'pneumococcal', 'staphylococcus', 'streptococcus',
    'mrsa', 'clostridium', 'c diff', 'tuberculosis', 'malaria',
    'vaccination', 'vaccine', 'immunization', 'prophylaxis',
    'sexually transmitted', 'sti', 'std', 'uti', 'urinary tract infection',
}

HEMATOLOGY_TERMS = {
    'hematology', 'hematologic', 'blood', 'hemoglobin', 'anemia',
    'thrombocytopenia', 'platelet', 'coagulation', 'bleeding disorder',
    'hemophilia', 'von willebrand', 'thrombosis', 'anticoagulation',
    'leukemia', 'lymphoma', 'myeloma', 'myelodysplastic', 'mds',
    'bone marrow', 'stem cell transplant', 'transfusion', 'blood bank',
    'sickle cell', 'thalassemia', 'iron deficiency', 'ferritin',
    'neutropenia', 'pancytopenia', 'polycythemia', 'eosinophilia',
}

PSYCHIATRY_TERMS = {
    'psychiatry', 'psychiatric', 'mental health', 'depression', 'anxiety',
    'bipolar', 'schizophrenia', 'psychosis', 'psychotic', 'antipsychotic',
    'antidepressant', 'ssri', 'snri', 'benzodiazepine', 'mood disorder',
    'obsessive compulsive', 'ocd', 'ptsd', 'post-traumatic', 'panic',
    'phobia', 'eating disorder', 'anorexia', 'bulimia', 'adhd',
    'attention deficit', 'autism', 'cognitive behavioral', 'cbt',
    'psychotherapy', 'suicide', 'suicidal', 'self-harm', 'addiction',
    'substance abuse', 'alcoholism', 'opioid', 'withdrawal',
}

DERMATOLOGY_TERMS = {
    'dermatology', 'dermatologic', 'skin', 'cutaneous', 'epidermis',
    'psoriasis', 'eczema', 'atopic dermatitis', 'acne', 'rosacea',
    'melanoma', 'basal cell', 'squamous cell', 'skin cancer', 'mole',
    'urticaria', 'hives', 'pruritus', 'itching', 'rash',
    'alopecia', 'hair loss', 'vitiligo', 'hyperpigmentation',
    'wound healing', 'burn', 'ulcer', 'pressure injury', 'decubitus',
    'topical', 'moisturizer', 'retinoid', 'phototherapy',
}

OPHTHALMOLOGY_TERMS = {
    'ophthalmology', 'ophthalmic', 'eye', 'ocular', 'vision',
    'glaucoma', 'cataract', 'macular degeneration', 'amd', 'retina',
    'diabetic retinopathy', 'retinal', 'vitreous', 'cornea', 'corneal',
    'uveitis', 'conjunctivitis', 'keratitis', 'dry eye', 'blepharitis',
    'intraocular pressure', 'iop', 'visual acuity', 'blindness',
    'lasik', 'phacoemulsification', 'intravitreal', 'anti-vegf',
}

ORTHOPEDICS_TERMS = {
    'orthopedic', 'orthopaedic', 'musculoskeletal', 'bone', 'fracture',
    'joint replacement', 'arthroplasty', 'hip replacement', 'knee replacement',
    'spine', 'spinal', 'vertebral', 'disc herniation', 'scoliosis',
    'tendon', 'ligament', 'acl', 'meniscus', 'rotator cuff',
    'carpal tunnel', 'osteoporosis', 'bone density', 'dexa',
    'physical therapy', 'rehabilitation', 'prosthesis', 'implant',
}

UROLOGY_TERMS = {
    'urology', 'urologic', 'urinary', 'bladder', 'prostate',
    'benign prostatic hyperplasia', 'bph', 'prostate cancer', 'psa',
    'kidney stone', 'nephrolithiasis', 'urolithiasis', 'cystitis',
    'incontinence', 'overactive bladder', 'erectile dysfunction',
    'testosterone', 'infertility', 'vasectomy', 'cystoscopy',
}

OBSTETRICS_GYNECOLOGY_TERMS = {
    'obstetrics', 'gynecology', 'obgyn', 'pregnancy', 'pregnant',
    'maternal', 'fetal', 'prenatal', 'antenatal', 'postnatal',
    'cesarean', 'c-section', 'vaginal delivery', 'labor', 'preterm',
    'preeclampsia', 'gestational diabetes', 'placenta', 'miscarriage',
    'fertility', 'ivf', 'in vitro', 'ovulation', 'endometriosis',
    'uterine', 'ovarian', 'cervical', 'pap smear', 'hysterectomy',
    'menstrual', 'menopause', 'hormone replacement', 'contraception',
}

PEDIATRICS_TERMS = {
    'pediatric', 'paediatric', 'child', 'children', 'infant', 'neonatal',
    'neonate', 'newborn', 'adolescent', 'childhood', 'juvenile',
    'developmental', 'growth', 'vaccination', 'immunization',
    'congenital', 'genetic', 'inherited', 'pediatric cancer',
    'nicu', 'preterm infant', 'low birth weight', 'failure to thrive',
}

GERIATRICS_TERMS = {
    'geriatric', 'elderly', 'older adult', 'aging', 'ageing',
    'frailty', 'sarcopenia', 'falls', 'fall prevention', 'polypharmacy',
    'nursing home', 'long-term care', 'dementia', 'alzheimer',
    'end of life', 'palliative', 'hospice', 'functional decline',
}

EMERGENCY_MEDICINE_TERMS = {
    'emergency medicine', 'emergency department', 'ed', 'trauma',
    'resuscitation', 'cpr', 'cardiac arrest', 'critical care',
    'intensive care', 'icu', 'acute care', 'triage', 'sepsis',
    'shock', 'hemorrhage', 'poisoning', 'overdose', 'intubation',
}

ANESTHESIOLOGY_TERMS = {
    'anesthesia', 'anaesthesia', 'anesthesiology', 'anesthetic',
    'sedation', 'general anesthesia', 'regional anesthesia', 'epidural',
    'spinal anesthesia', 'nerve block', 'pain management', 'postoperative',
    'intraoperative', 'propofol', 'fentanyl', 'neuromuscular block',
}

RADIOLOGY_TERMS = {
    'radiology', 'radiologic', 'imaging', 'ct scan', 'computed tomography',
    'mri', 'magnetic resonance', 'ultrasound', 'x-ray', 'pet scan',
    'interventional radiology', 'angiography', 'mammography', 'fluoroscopy',
    'contrast', 'gadolinium', 'radiation dose', 'image-guided',
}

ALLERGY_IMMUNOLOGY_TERMS = {
    'allergy', 'allergic', 'immunology', 'immune', 'immunodeficiency',
    'anaphylaxis', 'hypersensitivity', 'food allergy', 'drug allergy',
    'allergic rhinitis', 'hay fever', 'asthma', 'immunotherapy',
    'desensitization', 'ige', 'histamine', 'antihistamine', 'epinephrine',
}

PAIN_MEDICINE_TERMS = {
    'pain medicine', 'chronic pain', 'pain management', 'analgesic',
    'opioid', 'non-opioid', 'neuropathic pain', 'nociceptive',
    'back pain', 'neck pain', 'fibromyalgia', 'complex regional',
    'nerve block', 'epidural steroid', 'spinal cord stimulation',
}

PHYSICAL_MEDICINE_TERMS = {
    'physical medicine', 'rehabilitation', 'physiatry', 'pmr',
    'physical therapy', 'occupational therapy', 'speech therapy',
    'stroke rehabilitation', 'spinal cord injury', 'traumatic brain',
    'amputation', 'prosthetics', 'orthotics', 'gait training',
}

# Combine all specialty terms into a dictionary for classification
MEDICAL_SPECIALTY_TERMS = {
    'Cardiology': CARDIOLOGY_TERMS,
    'Gastroenterology': GASTROENTEROLOGY_TERMS,
    'Oncology': ONCOLOGY_TERMS,
    'Pulmonology': PULMONOLOGY_TERMS,
    'Neurology': NEUROLOGY_TERMS,
    'Nephrology': NEPHROLOGY_TERMS,
    'Endocrinology': ENDOCRINOLOGY_TERMS,
    'Rheumatology': RHEUMATOLOGY_TERMS,
    'Infectious Disease': INFECTIOUS_DISEASE_TERMS,
    'Hematology': HEMATOLOGY_TERMS,
    'Psychiatry': PSYCHIATRY_TERMS,
    'Dermatology': DERMATOLOGY_TERMS,
    'Ophthalmology': OPHTHALMOLOGY_TERMS,
    'Orthopedics': ORTHOPEDICS_TERMS,
    'Urology': UROLOGY_TERMS,
    'Obstetrics/Gynecology': OBSTETRICS_GYNECOLOGY_TERMS,
    'Pediatrics': PEDIATRICS_TERMS,
    'Geriatrics': GERIATRICS_TERMS,
    'Emergency Medicine': EMERGENCY_MEDICINE_TERMS,
    'Anesthesiology': ANESTHESIOLOGY_TERMS,
    'Radiology': RADIOLOGY_TERMS,
    'Allergy/Immunology': ALLERGY_IMMUNOLOGY_TERMS,
    'Pain Medicine': PAIN_MEDICINE_TERMS,
    'Physical Medicine/Rehabilitation': PHYSICAL_MEDICINE_TERMS,
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


def get_default_api_keys() -> dict:
    """Get API keys from environment variables."""
    return {
        'ncbi': os.environ.get('NCBI_API_KEY'),
        'semantic_scholar': os.environ.get('SEMANTIC_SCHOLAR_API_KEY'),
        'scopus': os.environ.get('SCOPUS_API_KEY'),
        'wos': os.environ.get('WOS_API_KEY'),
        'dimensions': os.environ.get('DIMENSIONS_API_KEY'),
    }
