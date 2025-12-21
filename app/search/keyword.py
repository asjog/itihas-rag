"""
Keyword search implementation using Xapian with RapidFuzz reranking.

This module provides fast keyword search with fuzzy matching capabilities
to handle OCR errors in the Marathi text corpus.
"""

import json
from pathlib import Path
from typing import Optional

import xapian
from rapidfuzz import fuzz

from app.utils.normalize import MarathiNormalizer, get_normalizer


class KeywordSearcher:
    """
    Keyword search engine using Xapian with RapidFuzz reranking.
    
    Features:
    - Fast full-text search using Xapian
    - Fuzzy matching with RapidFuzz for OCR robustness
    - Combined scoring for better relevance
    - Support for both English and Devanagari queries
    """
    
    def __init__(self, index_path: str | Path):
        """
        Initialize the searcher with a Xapian index.
        
        Args:
            index_path: Path to the Xapian index directory
        """
        self.index_path = Path(index_path)
        self.xapian_db_path = self.index_path / "xapian_db"
        
        self._db: Optional[xapian.Database] = None
        self._normalizer = get_normalizer()
        
        # Scoring weights
        self.xapian_weight = 0.7
        self.fuzzy_weight = 0.3
    
    @property
    def db(self) -> xapian.Database:
        """Lazy-load the Xapian database."""
        if self._db is None:
            if not self.xapian_db_path.exists():
                raise FileNotFoundError(
                    f"Xapian index not found at {self.xapian_db_path}. "
                    "Run scripts/index_corpus.py first."
                )
            self._db = xapian.Database(str(self.xapian_db_path))
        return self._db
    
    def reload_index(self) -> None:
        """Reload the Xapian index (useful after re-indexing)."""
        if self._db is not None:
            self._db.close()
            self._db = None
        # Re-open on next access
    
    @property
    def document_count(self) -> int:
        """Get the number of documents in the index."""
        try:
            return self.db.get_doccount()
        except Exception:
            return 0
    
    @property
    def is_loaded(self) -> bool:
        """Check if the index is loaded and available."""
        try:
            _ = self.db
            return True
        except Exception:
            return False
    
    def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        use_fuzzy_rerank: bool = True
    ) -> list[dict]:
        """
        Search the corpus for matching documents.
        
        Args:
            query: Search query (English or Devanagari)
            limit: Maximum number of results to return
            offset: Offset for pagination
            use_fuzzy_rerank: Whether to apply RapidFuzz reranking
            
        Returns:
            List of search results with scores and metadata
        """
        if not query or not query.strip():
            return []
        
        # Normalize the query
        normalized_query = self._normalizer.normalize(query)
        
        # Set up query parser
        qp = xapian.QueryParser()
        qp.set_database(self.db)
        qp.set_stemmer(xapian.Stem("none"))  # No stemming for Marathi
        
        # Parse the query with automatic wildcards for partial matching
        # FLAG_PARTIAL allows prefix matching
        flags = (
            xapian.QueryParser.FLAG_DEFAULT |
            xapian.QueryParser.FLAG_PARTIAL |
            xapian.QueryParser.FLAG_WILDCARD
        )
        
        try:
            xapian_query = qp.parse_query(normalized_query, flags)
        except xapian.QueryParserError:
            # Fallback to simple query if parsing fails
            xapian_query = qp.parse_query(normalized_query)
        
        # Execute the search
        enquire = xapian.Enquire(self.db)
        enquire.set_query(xapian_query)
        
        # Get extra results for reranking if fuzzy is enabled
        fetch_limit = limit * 3 if use_fuzzy_rerank else limit
        matches = enquire.get_mset(0, fetch_limit + offset)
        
        # Process results
        results = []
        for match in matches:
            try:
                # Parse document data
                doc_data = match.document.get_data()
                if isinstance(doc_data, bytes):
                    doc_data = doc_data.decode('utf-8')
                
                data = json.loads(doc_data)
                
                # Get content for fuzzy matching
                content = data.get("content", "")
                content_preview = data.get("content_preview", content[:500])
                
                # Calculate Xapian score (normalize to 0-100 range)
                xapian_score = match.weight
                max_weight = matches.get_max_possible() or 1
                xapian_score_normalized = (xapian_score / max_weight) * 100
                
                # Calculate fuzzy score if enabled
                if use_fuzzy_rerank:
                    # Use partial_ratio for substring matching
                    fuzzy_score = fuzz.partial_ratio(query, content_preview)
                else:
                    fuzzy_score = 0
                
                # Calculate combined score
                if use_fuzzy_rerank:
                    combined_score = (
                        xapian_score_normalized * self.xapian_weight +
                        fuzzy_score * self.fuzzy_weight
                    )
                else:
                    combined_score = xapian_score_normalized
                
                results.append({
                    "file_path": data.get("file_path", ""),
                    "page_number": data.get("page_number"),
                    "content": content,
                    "content_preview": content_preview,
                    "xapian_score": round(xapian_score_normalized, 2),
                    "fuzzy_score": round(fuzzy_score, 2),
                    "combined_score": round(combined_score, 2),
                    "doc_id": match.docid
                })
                
            except (json.JSONDecodeError, KeyError, AttributeError) as e:
                # Skip malformed documents
                continue
        
        # Sort by combined score if fuzzy reranking is enabled
        if use_fuzzy_rerank:
            results.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Apply pagination
        return results[offset:offset + limit]
    
    def search_exact(self, query: str, limit: int = 20) -> list[dict]:
        """
        Search for exact phrase matches.
        
        Args:
            query: Search phrase
            limit: Maximum number of results
            
        Returns:
            List of search results
        """
        if not query or not query.strip():
            return []
        
        normalized_query = self._normalizer.normalize(query)
        
        # Create a phrase query
        qp = xapian.QueryParser()
        qp.set_database(self.db)
        
        # Use phrase query for exact matching
        flags = xapian.QueryParser.FLAG_PHRASE
        
        try:
            xapian_query = qp.parse_query(f'"{normalized_query}"', flags)
        except xapian.QueryParserError:
            return []
        
        enquire = xapian.Enquire(self.db)
        enquire.set_query(xapian_query)
        matches = enquire.get_mset(0, limit)
        
        results = []
        for match in matches:
            try:
                doc_data = match.document.get_data()
                if isinstance(doc_data, bytes):
                    doc_data = doc_data.decode('utf-8')
                
                data = json.loads(doc_data)
                
                results.append({
                    "file_path": data.get("file_path", ""),
                    "page_number": data.get("page_number"),
                    "content": data.get("content", ""),
                    "content_preview": data.get("content_preview", ""),
                    "xapian_score": round(match.weight, 2),
                    "fuzzy_score": 100.0,  # Exact match
                    "combined_score": round(match.weight, 2),
                    "doc_id": match.docid
                })
            except Exception:
                continue
        
        return results
    
    def highlight_matches(
        self,
        text: str,
        query: str,
        before_tag: str = "<mark>",
        after_tag: str = "</mark>"
    ) -> str:
        """
        Highlight query terms in text.
        
        Args:
            text: Text to highlight
            query: Query terms to highlight
            before_tag: HTML tag to insert before match
            after_tag: HTML tag to insert after match
            
        Returns:
            Text with highlighted matches
        """
        if not text or not query:
            return text
        
        # Normalize query and split into terms
        normalized_query = self._normalizer.normalize(query)
        terms = normalized_query.split()
        
        result = text
        for term in terms:
            if len(term) < 2:  # Skip very short terms
                continue
            
            # Case-insensitive replacement
            import re
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            result = pattern.sub(f"{before_tag}\\g<0>{after_tag}", result)
        
        return result


# Singleton instance
_searcher_instance: Optional[KeywordSearcher] = None


def get_searcher(index_path: str = "./indexes") -> KeywordSearcher:
    """
    Get the singleton KeywordSearcher instance.
    
    Args:
        index_path: Path to the Xapian index
        
    Returns:
        KeywordSearcher instance
    """
    global _searcher_instance
    if _searcher_instance is None:
        _searcher_instance = KeywordSearcher(index_path)
    return _searcher_instance

