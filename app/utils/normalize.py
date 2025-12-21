"""Unicode + Indic normalization pipeline for Marathi text."""

import unicodedata
import re
from functools import lru_cache

# Try to import indic_nlp_library, with fallback if not available
try:
    from indicnlp.normalize.indic_normalize import IndicNormalizerFactory
    INDIC_NLP_AVAILABLE = True
except ImportError:
    INDIC_NLP_AVAILABLE = False


class MarathiNormalizer:
    """
    Normalizer for Marathi/Devanagari text.
    
    Handles:
    - Unicode NFKC normalization
    - Indic-specific normalization (nukta, matras, anusvara/chandrabindu)
    - Multi-variant generation for OCR robustness
    """
    
    def __init__(self):
        """Initialize the normalizer with Indic NLP library if available."""
        if INDIC_NLP_AVAILABLE:
            factory = IndicNormalizerFactory()
            self._indic_normalizer = factory.get_normalizer("mr")
        else:
            self._indic_normalizer = None
        
        # Common Devanagari character variations for OCR robustness
        # Maps common OCR errors to their correct forms
        self._char_mappings = {
            # Nukta variations
            '\u0929': '\u0928',  # ऩ -> न (na with nukta -> na)
            '\u0931': '\u0930',  # ऱ -> र (ra with nukta -> ra)
            '\u0934': '\u0933',  # ऴ -> ळ (llla -> lla)
            # Anusvara/Chandrabindu equivalence (context-dependent)
            # '\u0901': '\u0902',  # Chandrabindu -> Anusvara (optional)
        }
        
        # Regex for multiple spaces/whitespace normalization
        self._whitespace_re = re.compile(r'\s+')
        
        # Devanagari Unicode range for detection
        self._devanagari_re = re.compile(r'[\u0900-\u097F]')
    
    def normalize(self, text: str) -> str:
        """
        Apply full normalization pipeline to text.
        
        Args:
            text: Input text (can be Marathi, English, or mixed)
            
        Returns:
            Normalized text
        """
        if not text:
            return text
        
        # Step 1: Unicode NFKC normalization
        # This standardizes composed/decomposed characters
        text = unicodedata.normalize("NFKC", text)
        
        # Step 2: Apply character mappings for OCR robustness
        for old_char, new_char in self._char_mappings.items():
            text = text.replace(old_char, new_char)
        
        # Step 3: Indic-specific normalization (if available)
        if self._indic_normalizer is not None:
            try:
                text = self._indic_normalizer.normalize(text)
            except Exception:
                # Fallback if Indic normalizer fails
                pass
        
        # Step 4: Normalize whitespace
        text = self._whitespace_re.sub(' ', text).strip()
        
        return text
    
    def normalize_query(self, query: str) -> str:
        """
        Normalize a search query.
        
        Args:
            query: Search query in English or Devanagari
            
        Returns:
            Normalized query
        """
        return self.normalize(query)
    
    def get_variants(self, text: str) -> list[str]:
        """
        Generate multiple indexable variants for OCR robustness.
        
        This allows matching despite OCR errors by indexing multiple
        normalized forms of the same text.
        
        Args:
            text: Original text
            
        Returns:
            List of text variants for indexing
        """
        variants = []
        
        # Original text (for exact matching)
        if text:
            variants.append(text)
        
        # Normalized form
        normalized = self.normalize(text)
        if normalized and normalized not in variants:
            variants.append(normalized)
        
        # Lowercased form (helps with English text in mixed documents)
        lowered = normalized.lower() if normalized else ""
        if lowered and lowered not in variants:
            variants.append(lowered)
        
        return variants
    
    def is_devanagari(self, text: str) -> bool:
        """
        Check if text contains Devanagari characters.
        
        Args:
            text: Input text
            
        Returns:
            True if text contains Devanagari characters
        """
        return bool(self._devanagari_re.search(text)) if text else False
    
    def extract_devanagari(self, text: str) -> str:
        """
        Extract only Devanagari characters and basic punctuation from text.
        
        Args:
            text: Input text
            
        Returns:
            Text with only Devanagari characters and spaces
        """
        if not text:
            return ""
        
        # Keep Devanagari characters, spaces, and basic punctuation
        result = []
        for char in text:
            if self._devanagari_re.match(char) or char in ' \t\n।॥,.!?':
                result.append(char)
        
        return ''.join(result)


# Singleton instance for reuse
_normalizer_instance = None


def get_normalizer() -> MarathiNormalizer:
    """Get the singleton MarathiNormalizer instance."""
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = MarathiNormalizer()
    return _normalizer_instance


@lru_cache(maxsize=1024)
def normalize_text(text: str) -> str:
    """
    Cached normalization function for frequent queries.
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text
    """
    return get_normalizer().normalize(text)

