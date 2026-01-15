"""
Semantic search implementation using Gemini embeddings and ChromaDB.

This module provides AI-powered semantic search with bilingual source references
for the Marathi history corpus.
"""

import os
import requests
from pathlib import Path
from typing import List, Dict, Optional

import chromadb
from chromadb.config import Settings


class SemanticSearcher:
    """
    Semantic search engine using Gemini embeddings and ChromaDB.

    Features:
    - Gemini embedding-based semantic search (768-dim vectors)
    - ChromaDB vector database integration
    - AI-powered summarization using Gemini 2.5 Flash
    - Bilingual references (English + Marathi sources)
    """

    # Configuration - must match generate_gemini_embeddings.py
    EMBEDDING_MODEL = "gemini-embedding-001"
    SUMMARY_MODEL = "gemini-2.5-flash-lite"
    TASK_TYPE = "RETRIEVAL_QUERY"
    DIMENSION = 768

    def __init__(self, vectors_dir: Path, collection_name: str = "marathi_history"):
        """
        Initialize the semantic searcher with ChromaDB.

        Args:
            vectors_dir: Path to the ChromaDB vectors directory
            collection_name: Name of the ChromaDB collection
        """
        self.vectors_dir = Path(vectors_dir)
        self.collection_name = collection_name

        self._client: Optional[chromadb.ClientAPI] = None
        self._collection: Optional[chromadb.Collection] = None
        self._api_key: Optional[str] = None

    @property
    def api_key(self) -> str:
        """Lazy-load API key from environment."""
        if self._api_key is None:
            self._api_key = os.getenv("GOOGLE_API_KEY")
            if not self._api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not set")
        return self._api_key

    @property
    def client(self) -> chromadb.ClientAPI:
        """Lazy-load the ChromaDB client."""
        if self._client is None:
            if not self.vectors_dir.exists():
                raise FileNotFoundError(
                    f"ChromaDB vectors directory not found at {self.vectors_dir}"
                )
            self._client = chromadb.PersistentClient(
                path=str(self.vectors_dir),
                settings=Settings(anonymized_telemetry=False)
            )
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        """Lazy-load the ChromaDB collection."""
        if self._collection is None:
            self._collection = self.client.get_collection(name=self.collection_name)
        return self._collection

    @property
    def chunk_count(self) -> int:
        """Get the number of chunks in the collection."""
        try:
            return self.collection.count()
        except Exception:
            return 0

    @property
    def is_loaded(self) -> bool:
        """Check if the collection is loaded and available."""
        try:
            _ = self.collection
            return True
        except Exception:
            return False

    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a search query using Gemini API.

        Args:
            query: Search query text

        Returns:
            768-dimensional embedding vector

        Raises:
            Exception: If embedding generation fails
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.EMBEDDING_MODEL}:embedContent?key={self.api_key}"

        body = {
            "model": f"models/{self.EMBEDDING_MODEL}",
            "content": {
                "parts": [{"text": query}]
            },
            "taskType": self.TASK_TYPE,
            "outputDimensionality": self.DIMENSION
        }

        resp = requests.post(url, json=body, timeout=30)

        if resp.status_code != 200:
            raise Exception(f"Embedding API error: {resp.text}")

        result = resp.json()
        embedding = result.get("embedding", {}).get("values", [])

        if not embedding:
            raise Exception("No embedding returned from API")

        return embedding

    def search(
        self,
        query: str,
        limit: int = 20,
        include_summary: bool = True
    ) -> Dict:
        """
        Search the corpus using semantic similarity.

        Args:
            query: Search query (English or Marathi)
            limit: Maximum number of results to return (1-100)
            include_summary: Whether to generate AI summary

        Returns:
            Dictionary with query, results, total, and optional summary
        """
        if not query or not query.strip():
            return {
                "query": query,
                "results": [],
                "total": 0,
                "summary": None
            }

        # Generate query embedding
        try:
            query_embedding = self.embed_query(query)
        except Exception as e:
            raise Exception(f"Failed to generate query embedding: {str(e)}")

        # Query ChromaDB
        results_data = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit, 100),
            include=["metadatas", "documents", "distances"]
        )

        # Process results
        results = []
        context_texts = []

        for i, (chunk_id, meta, doc_text, distance) in enumerate(zip(
            results_data["ids"][0],
            results_data["metadatas"][0],
            results_data["documents"][0],
            results_data["distances"][0]
        )):
            # Calculate similarity percentage
            similarity = round((1 - distance) * 100, 2)

            # Extract chunk index from chunk_id (format: "book_chunk_N")
            chunk_index = int(chunk_id.split("_chunk_")[-1])

            # Build result
            result = {
                "chunk_id": chunk_id,
                "text": doc_text,
                "book": meta.get("book_name", "unknown"),
                "source_file": meta.get("source_file", ""),
                "marathi_source_file": meta.get("marathi_source_file", ""),
                "chunk_index": chunk_index,
                "char_count": meta.get("char_count", 0),
                "page_range": meta.get("page_range", ""),
                "distance": round(distance, 4),
                "similarity": similarity
            }
            results.append(result)

            # Prepare context for summary
            if include_summary:
                marathi_ref = f" | Marathi: {meta.get('marathi_source_file')}" if meta.get('marathi_source_file') else ""
                page_ref = f" | Pages: {meta.get('page_range')}" if meta.get('page_range') else ""
                context_texts.append(
                    f"[English: {meta.get('source_file', 'unknown')}{marathi_ref}{page_ref}]\n{doc_text}"
                )

        # Generate summary if requested
        summary = None
        if include_summary and context_texts:
            try:
                summary = self.generate_summary(query, context_texts)
            except Exception as e:
                summary = f"Error generating summary: {str(e)[:200]}"

        return {
            "query": query,
            "results": results,
            "total": len(results),
            "summary": summary
        }

    def generate_summary(self, query: str, contexts: List[str]) -> str:
        """
        Generate a coherent summary from retrieved contexts using Gemini 2.5 Flash.

        Args:
            query: Original user query
            contexts: List of context strings with source references

        Returns:
            AI-generated summary text
        """
        if not contexts:
            return "No relevant documents found to summarize."

        # Combine contexts
        combined_context = "\n\n---\n\n".join(contexts)

        # Create the prompt
        prompt = f"""You are a historian analyzing historical documents about Marathi history (मराठा इतिहास).

Based on the following retrieved document excerpts, provide a comprehensive and coherent summary answering the user's query.

**Instructions:**
1. Organize the information chronologically by dates/events when possible
2. Include specific dates, names, and places mentioned in the sources
3. Some information in the context will be in quotes or a part of a letter. In the output summary
mention that this information is from a letter of quote by the author or speaker.
4. If there are contradictions or uncertainties, note them
5. Write in clear, flowing prose (not bullet points)
6. If the context doesn't contain relevant information for the query, say so honestly
7. Focus on accuracy - only include information found in the provided context
8. If there are interesting factoids or trivia, include them in the output.
9. If there is no matching information in the context, say so honestly and do not use any
other external knowledge to answer the query.

**User Query:** {query}

**Retrieved Historical Documents:**
{combined_context}

**Summary (organized chronologically when dates are available):**"""

        # Estimate input tokens (~4 chars per token) and set output to 25%
        # Minimum 4000 tokens to ensure complete summaries
        estimated_input_tokens = len(prompt) // 4
        output_tokens = max(4000, min(8192, int(estimated_input_tokens * 0.25)))

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.SUMMARY_MODEL}:generateContent?key={self.api_key}"

        body = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": output_tokens
            }
        }

        try:
            resp = requests.post(url, json=body, timeout=120)

            if resp.status_code != 200:
                return f"Error generating summary: {resp.text[:200]}"

            result = resp.json()
            candidates = result.get("candidates", [])

            if candidates:
                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])
                summary = "".join(p.get("text", "") for p in parts)

                # Check if response was truncated
                finish_reason = candidate.get("finishReason", "")

                if finish_reason == "MAX_TOKENS":
                    summary += "\n\n[Note: Summary was truncated due to length limits]"
                elif finish_reason == "SAFETY":
                    summary += "\n\n[Note: Summary was stopped due to safety filters]"
                elif finish_reason not in ["STOP", "", "FINISH_REASON_STOP"]:
                    summary += f"\n\n[Note: Generation ended with reason: {finish_reason}]"

                return summary.strip()

            # Check for errors in response
            error = result.get("error", {})
            if error:
                return f"API error: {error.get('message', 'Unknown error')}"

            return "No summary generated (empty response)"

        except requests.Timeout:
            return "Summary generation timed out after 120 seconds"
        except Exception as e:
            return f"Error generating summary: {str(e)[:200]}"


# Singleton instance
_searcher_instance: Optional[SemanticSearcher] = None


def get_searcher(vectors_dir: Path = Path("vectors")) -> SemanticSearcher:
    """
    Get the singleton SemanticSearcher instance.

    Args:
        vectors_dir: Path to the ChromaDB vectors directory

    Returns:
        SemanticSearcher instance
    """
    global _searcher_instance
    if _searcher_instance is None:
        _searcher_instance = SemanticSearcher(vectors_dir)
    return _searcher_instance
