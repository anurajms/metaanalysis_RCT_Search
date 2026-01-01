"""
LLM-based topic classification using LM Studio.
Connects to local LM Studio server for improved classification accuracy.
"""

import json
import requests
from typing import Optional, Dict, List, Tuple
import time

# LM Studio default endpoint
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

# All medical specialties for classification
MEDICAL_SPECIALTIES = [
    'Cardiology', 'Gastroenterology', 'Oncology', 'Pulmonology',
    'Neurology', 'Nephrology', 'Endocrinology', 'Rheumatology',
    'Infectious Disease', 'Hematology', 'Psychiatry', 'Dermatology',
    'Ophthalmology', 'Orthopedics', 'Urology', 'Obstetrics/Gynecology',
    'Pediatrics', 'Geriatrics', 'Emergency Medicine', 'Anesthesiology',
    'Radiology', 'Allergy/Immunology', 'Pain Medicine', 
    'Physical Medicine/Rehabilitation', 'Other/Unclear'
]


def check_lm_studio_connection() -> bool:
    """Check if LM Studio is running and accessible."""
    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=5)
        return response.status_code == 200
    except:
        return False


def get_available_models() -> List[Dict]:
    """Get all available models from LM Studio."""
    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        return []
    except:
        return []


def get_loaded_model() -> Optional[str]:
    """Get the currently loaded model in LM Studio."""
    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                return data['data'][0].get('id', 'Unknown model')
        return None
    except:
        return None


def classify_with_llm(
    title: str, 
    abstract: str, 
    mesh_terms: List[str] = None,
    keywords: List[str] = None,
    journal: str = None,
    current_topic: str = None,
    temperature: float = 0.1,
    model_id: str = "local-model"
) -> Tuple[str, str, float]:
    """
    Classify a paper into a medical specialty using LLM.
    
    Args:
        title: Paper title
        abstract: Paper abstract
        mesh_terms: List of MeSH terms
        keywords: List of keywords
        journal: Journal name
        current_topic: Current rules-based classification (for context)
        temperature: LLM temperature (lower = more deterministic)
    
    Returns:
        Tuple of (specialty, reasoning, confidence)
    """
    # Build context
    context_parts = []
    if mesh_terms:
        context_parts.append(f"MeSH Terms: {', '.join(mesh_terms[:10])}")
    if keywords:
        context_parts.append(f"Keywords: {', '.join(keywords[:10])}")
    if journal:
        context_parts.append(f"Journal: {journal}")
    if current_topic:
        context_parts.append(f"Initial classification (rules-based): {current_topic}")
    
    context = "\n".join(context_parts) if context_parts else "No additional context available."
    
    # Build prompt
    specialties_list = "\n".join([f"- {s}" for s in MEDICAL_SPECIALTIES])
    
    prompt = f"""You are a medical research classifier. Classify the following research paper into exactly ONE of these medical specialties:

{specialties_list}

PAPER INFORMATION:
Title: {title}

Abstract: {abstract[:1500] if abstract else "No abstract available."}

Additional Context:
{context}

INSTRUCTIONS:
1. Select the SINGLE most appropriate specialty from the list above
2. Provide brief reasoning (1-2 sentences)
3. Rate your confidence from 0.0 to 1.0

Respond ONLY in this exact JSON format:
{{"specialty": "SPECIALTY_NAME", "reasoning": "Brief explanation", "confidence": 0.XX}}"""

    try:
        response = requests.post(
            LM_STUDIO_URL,
            json={
                "model": model_id,
                "messages": [
                    {"role": "system", "content": "You are a medical research classification expert. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": 200,
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            
            # Parse JSON response
            # Handle potential markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            parsed = json.loads(content)
            
            specialty = parsed.get('specialty', 'Other/Unclear')
            reasoning = parsed.get('reasoning', 'No reasoning provided')
            confidence = float(parsed.get('confidence', 0.5))
            
            # Validate specialty is in our list
            if specialty not in MEDICAL_SPECIALTIES:
                # Try to find closest match
                specialty_lower = specialty.lower()
                for valid_spec in MEDICAL_SPECIALTIES:
                    if valid_spec.lower() in specialty_lower or specialty_lower in valid_spec.lower():
                        specialty = valid_spec
                        break
                else:
                    specialty = 'Other/Unclear'
            
            return specialty, reasoning, confidence
            
        else:
            return 'Other/Unclear', f"LLM error: {response.status_code}", 0.0
            
    except json.JSONDecodeError as e:
        return 'Other/Unclear', f"Failed to parse LLM response: {str(e)}", 0.0
    except requests.exceptions.Timeout:
        return 'Other/Unclear', "LLM request timed out", 0.0
    except Exception as e:
        return 'Other/Unclear', f"LLM error: {str(e)}", 0.0


def refine_classification_with_llm(records: list, progress_callback=None, model_id: str = "local-model") -> list:
    """
    Refine classification for all records using LLM.
    
    Args:
        records: List of RCTRecord objects with initial classification
        progress_callback: Optional callback function(current, total, record_title)
        model_id: The LM Studio model ID to use for classification
    
    Returns:
        List of records with updated classification fields
    """
    total = len(records)
    
    for idx, record in enumerate(records):
        if progress_callback:
            progress_callback(idx + 1, total, record.title[:50] if record.title else "Unknown")
        
        # Get LLM classification
        new_topic, reasoning, confidence = classify_with_llm(
            title=record.title or "",
            abstract=record.abstract or "",
            mesh_terms=record.mesh_terms,
            keywords=record.keywords,
            journal=record.journal,
            current_topic=record.topic,
            model_id=model_id
        )
        
        # Update record with LLM results
        record.llm_topic = new_topic
        record.llm_reasoning = reasoning
        record.llm_confidence = confidence
        
        # Use LLM topic if confidence is high enough, otherwise keep original
        if confidence >= 0.7:
            record.final_topic = new_topic
            record.topic_source = "LLM"
        else:
            record.final_topic = record.topic
            record.topic_source = "Rules (LLM low confidence)"
        
        # Small delay to avoid overwhelming the LLM
        time.sleep(0.1)
    
    return records


def save_llm_refined_results(records: list, output_path: str) -> str:
    """
    Save LLM-refined results to a new Excel file.
    
    Args:
        records: List of RCTRecord objects with LLM classification
        output_path: Base output path (will add _llm_refined suffix)
    
    Returns:
        Path to the saved file
    """
    import pandas as pd
    from pathlib import Path
    
    # Create output filename
    base_path = Path(output_path)
    llm_path = base_path.parent / f"{base_path.stem}_llm_refined.xlsx"
    
    # Build DataFrame
    data = []
    for record in records:
        row = {
            'pmid': record.pmid,
            'title': record.title,
            'journal': record.journal,
            'publication_date': record.publication_date,
            'original_topic': record.topic,
            'original_reason': record.classification_reason,
            'llm_topic': getattr(record, 'llm_topic', ''),
            'llm_reasoning': getattr(record, 'llm_reasoning', ''),
            'llm_confidence': getattr(record, 'llm_confidence', 0.0),
            'final_topic': getattr(record, 'final_topic', record.topic),
            'topic_source': getattr(record, 'topic_source', 'Rules'),
            'abstract': record.abstract[:500] if record.abstract else '',
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # Save with formatting
    with pd.ExcelWriter(llm_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='LLM Refined')
        
        # Auto-adjust column widths
        worksheet = writer.sheets['LLM Refined']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    return str(llm_path)
