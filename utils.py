"""
Utility functions for rate limiting, date handling, and logging.
"""

import time
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable, Any
import threading

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('rct_finder')


class RateLimiter:
    """Thread-safe rate limiter for API calls."""
    
    def __init__(self, requests_per_second: float):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self.lock = threading.Lock()
    
    def wait(self):
        """Wait if necessary to respect rate limit."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self.last_request_time = time.time()
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply rate limiting to a function."""
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            self.wait()
            return func(*args, **kwargs)
        return wrapper


def get_date_range(days: int) -> tuple[str, str]:
    """
    Get date range for search query.
    Returns (start_date, end_date) as YYYY-MM-DD strings.
    Uses UTC for timezone safety.
    """
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)
    return start_date.isoformat(), end_date.isoformat()


def get_pubmed_date_range(days: int) -> tuple[str, str]:
    """
    Get date range formatted for PubMed queries.
    Returns (start_date, end_date) as YYYY/MM/DD strings.
    """
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)
    return start_date.strftime("%Y/%m/%d"), end_date.strftime("%Y/%m/%d")


def parse_date(date_str: str) -> tuple[str, int]:
    """
    Parse various date formats and return (normalized_date, year).
    Handles: YYYY-MM-DD, YYYY/MM/DD, YYYY-MM, YYYY, etc.
    """
    if not date_str:
        return None, None
    
    date_str = date_str.strip()
    
    # Try various formats
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y-%m",
        "%Y/%m",
        "%Y",
        "%d %b %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str[:len(date_str)], fmt)
            return dt.strftime("%Y-%m-%d"), dt.year
        except ValueError:
            continue
    
    # Try to extract just the year
    import re
    year_match = re.search(r'(\d{4})', date_str)
    if year_match:
        year = int(year_match.group(1))
        return f"{year}-01-01", year
    
    return None, None


def normalize_doi(doi: str) -> str:
    """Normalize DOI to standard format (lowercase, no URL prefix)."""
    if not doi:
        return None
    
    doi = doi.strip().lower()
    
    # Remove URL prefixes
    prefixes = [
        'https://doi.org/',
        'http://doi.org/',
        'https://dx.doi.org/',
        'http://dx.doi.org/',
        'doi:',
    ]
    
    for prefix in prefixes:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
            break
    
    return doi if doi else None


def normalize_title(title: str) -> str:
    """Normalize title for comparison (lowercase, alphanumeric only)."""
    if not title:
        return ""
    return ''.join(c.lower() for c in title if c.isalnum())


def title_similarity(title1: str, title2: str) -> float:
    """
    Calculate similarity between two titles.
    Returns a score between 0 and 1.
    """
    if not title1 or not title2:
        return 0.0
    
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # Simple Jaccard-like similarity on character n-grams
    n = 3
    if len(norm1) < n or len(norm2) < n:
        return 1.0 if norm1 == norm2 else 0.0
    
    ngrams1 = set(norm1[i:i+n] for i in range(len(norm1) - n + 1))
    ngrams2 = set(norm2[i:i+n] for i in range(len(norm2) - n + 1))
    
    intersection = len(ngrams1 & ngrams2)
    union = len(ngrams1 | ngrams2)
    
    return intersection / union if union > 0 else 0.0


def chunk_list(lst: list, chunk_size: int) -> list:
    """Split a list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def safe_get(d: dict, *keys, default=None):
    """Safely get nested dictionary values."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d if d is not None else default
