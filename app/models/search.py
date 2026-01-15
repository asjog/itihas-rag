"""Pydantic models for search API."""

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    """Search query input model."""
    
    query: str = Field(..., min_length=1, description="Search query in English or Devanagari")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")


class SearchResult(BaseModel):
    """Individual search result."""
    
    file_path: str = Field(..., description="Path to the source file")
    page_number: int | None = Field(None, description="Page number in the book")
    content: str = Field(..., description="Text content or preview")
    xapian_score: float = Field(..., description="Xapian relevance score")
    fuzzy_score: float = Field(..., description="RapidFuzz similarity score")
    combined_score: float = Field(..., description="Combined ranking score")


class SearchResponse(BaseModel):
    """Search API response model."""
    
    query: str = Field(..., description="Original query")
    total_results: int = Field(..., description="Total number of results")
    results: list[SearchResult] = Field(default_factory=list, description="Search results")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="ok")
    index_loaded: bool = Field(..., description="Whether the search index is loaded")
    document_count: int = Field(default=0, description="Number of indexed documents")


class SemanticSearchResult(BaseModel):
    """Individual semantic search result."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="Text content of the chunk")
    book: str = Field(..., description="Book name")
    source_file: str = Field(..., description="English source file path")
    marathi_source_file: str = Field(default="", description="Marathi source file path")
    chunk_index: int = Field(..., description="Chunk index in the book")
    char_count: int = Field(..., description="Character count")
    page_range: str = Field(default="", description="Page range")
    distance: float = Field(..., description="Embedding distance (lower is better)")
    similarity: float = Field(..., description="Similarity percentage (0-100)")


class SemanticSearchResponse(BaseModel):
    """Semantic search API response model."""

    query: str = Field(..., description="Original query")
    results: list[SemanticSearchResult] = Field(default_factory=list, description="Search results")
    total: int = Field(..., description="Total number of results")
    summary: str | None = Field(None, description="AI-generated summary")

