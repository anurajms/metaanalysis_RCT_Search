"""
Base connector interface for data sources.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from ..models import RCTRecord


class BaseConnector(ABC):
    """Abstract base class for data source connectors."""
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the name of this data source."""
        pass
    
    @abstractmethod
    def search(
        self, 
        days: int, 
        query: Optional[str] = None,
        max_records: Optional[int] = None,
        include_preprints: bool = False
    ) -> List[str]:
        """
        Search for RCT papers published in the last N days.
        
        Args:
            days: Number of days to look back
            query: Optional additional query terms
            max_records: Maximum number of records to return
            include_preprints: Whether to include preprints
            
        Returns:
            List of paper IDs from this source
        """
        pass
    
    @abstractmethod
    def fetch_details(self, ids: List[str]) -> List[RCTRecord]:
        """
        Fetch detailed records for the given IDs.
        
        Args:
            ids: List of paper IDs from this source
            
        Returns:
            List of normalized RCTRecord objects
        """
        pass
    
    def search_and_fetch(
        self,
        days: int,
        query: Optional[str] = None,
        max_records: Optional[int] = None,
        include_preprints: bool = False
    ) -> List[RCTRecord]:
        """
        Convenience method to search and fetch in one call.
        """
        ids = self.search(days, query, max_records, include_preprints)
        if not ids:
            return []
        return self.fetch_details(ids)
