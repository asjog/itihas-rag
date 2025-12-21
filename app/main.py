"""
FastAPI application for Marathi Text Search.

Provides REST API endpoints for keyword and semantic search
in a Marathi text corpus.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.models.search import (
    HealthResponse,
    SearchQuery,
    SearchResponse,
    SearchResult,
)
from app.search.keyword import KeywordSearcher, get_searcher
from app.utils.context import extract_context

# Load environment variables
load_dotenv()

# Configuration - use absolute paths based on project root
PROJECT_ROOT = Path(__file__).parent.parent
INDEX_DIR = os.getenv("INDEX_DIR", str(PROJECT_ROOT / "indexes"))
DEFAULT_RESULT_LIMIT = int(os.getenv("DEFAULT_RESULT_LIMIT", "20"))

# Global searcher instance
searcher: Optional[KeywordSearcher] = None


def get_or_init_searcher() -> Optional[KeywordSearcher]:
    """Get or initialize the searcher."""
    global searcher
    if searcher is None:
        try:
            searcher = KeywordSearcher(INDEX_DIR)
        except Exception as e:
            print(f"⚠ Failed to load search index: {e}")
    return searcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - initialize resources on startup."""
    global searcher
    
    # Initialize the searcher
    try:
        searcher = KeywordSearcher(INDEX_DIR)
        if searcher.is_loaded:
            print(f"✓ Search index loaded: {searcher.document_count} documents")
        else:
            print("⚠ Search index not found. Run scripts/index_corpus.py first.")
    except Exception as e:
        print(f"⚠ Failed to load search index: {e}")
        searcher = None
    
    yield
    
    # Cleanup on shutdown
    if searcher is not None:
        searcher = None


# Create FastAPI app
app = FastAPI(
    title="Marathi Text Search API",
    description="Search API for Marathi text corpus with keyword and semantic search capabilities",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Frontend path
frontend_path = Path(__file__).parent.parent / "frontend"


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend or redirect to docs."""
    frontend_index = frontend_path / "index.html"
    if frontend_index.exists():
        return frontend_index.read_text(encoding="utf-8")
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Marathi Text Search API</title>
        <style>
            body { font-family: system-ui, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            a { color: #0066cc; }
            code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>मराठी शोध API</h1>
        <h2>Marathi Text Search API</h2>
        <p>Welcome to the Marathi Text Search API.</p>
        <ul>
            <li><a href="/docs">API Documentation (Swagger UI)</a></li>
            <li><a href="/redoc">API Documentation (ReDoc)</a></li>
            <li><a href="/api/health">Health Check</a></li>
        </ul>
        <h3>Quick Start</h3>
        <p>Search example:</p>
        <code>GET /api/search?query=शिवाजी महाराज</code>
    </body>
    </html>
    """


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns the status of the search service and index.
    """
    current_searcher = get_or_init_searcher()
    return HealthResponse(
        status="ok",
        index_loaded=current_searcher.is_loaded if current_searcher else False,
        document_count=current_searcher.document_count if current_searcher else 0,
    )


@app.get("/api/search", response_model=SearchResponse)
async def search(
    query: str = Query(..., min_length=1, description="Search query in English or Devanagari"),
    limit: int = Query(default=DEFAULT_RESULT_LIMIT, ge=1, le=100, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    fuzzy: bool = Query(default=True, description="Enable fuzzy matching for OCR robustness"),
):
    """
    Search the Marathi text corpus.
    
    Performs keyword search with optional fuzzy matching using RapidFuzz
    for handling OCR errors in scanned documents.
    
    - **query**: Search terms in English or Devanagari (Marathi)
    - **limit**: Maximum number of results (1-100)
    - **offset**: Pagination offset
    - **fuzzy**: Enable fuzzy matching for OCR robustness (default: true)
    """
    # Get or initialize searcher
    current_searcher = get_or_init_searcher()
    
    if current_searcher is None or not current_searcher.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Search index not available. Please run the indexer first."
        )
    
    try:
        results = current_searcher.search(
            query=query,
            limit=limit,
            offset=offset,
            use_fuzzy_rerank=fuzzy,
        )
        
        # Convert to response model - show full page content
        search_results = []
        for r in results:
            # Use full content from the indexed document
            full_content = r.get("content", r["content_preview"])
            
            search_results.append(
                SearchResult(
                    file_path=r["file_path"],
                    page_number=r.get("page_number"),
                    content=full_content,
                    xapian_score=r["xapian_score"],
                    fuzzy_score=r["fuzzy_score"],
                    combined_score=r["combined_score"],
                )
            )
        
        return SearchResponse(
            query=query,
            total_results=len(search_results),
            results=search_results,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@app.post("/api/search", response_model=SearchResponse)
async def search_post(search_query: SearchQuery):
    """
    Search the Marathi text corpus (POST method).
    
    Alternative endpoint for complex queries using POST.
    """
    return await search(
        query=search_query.query,
        limit=search_query.limit,
        offset=search_query.offset,
    )


@app.get("/api/search/exact", response_model=SearchResponse)
async def search_exact(
    query: str = Query(..., min_length=1, description="Exact phrase to search"),
    limit: int = Query(default=DEFAULT_RESULT_LIMIT, ge=1, le=100),
):
    """
    Search for exact phrase matches.
    
    Use this endpoint when you need exact phrase matching
    instead of keyword search.
    """
    current_searcher = get_or_init_searcher()
    
    if current_searcher is None or not current_searcher.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Search index not available."
        )
    
    try:
        results = current_searcher.search_exact(query=query, limit=limit)
        
        search_results = [
            SearchResult(
                file_path=r["file_path"],
                page_number=r.get("page_number"),
                content=r["content_preview"],
                xapian_score=r["xapian_score"],
                fuzzy_score=r["fuzzy_score"],
                combined_score=r["combined_score"],
            )
            for r in results
        ]
        
        return SearchResponse(
            query=query,
            total_results=len(search_results),
            results=search_results,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@app.get("/api/reload")
async def reload_index():
    """
    Reload the search index.
    
    Call this endpoint after re-indexing the corpus
    to pick up the new documents.
    """
    current_searcher = get_or_init_searcher()
    
    if current_searcher is None:
        raise HTTPException(status_code=503, detail="Searcher not initialized")
    
    try:
        current_searcher.reload_index()
        return {
            "status": "ok",
            "message": "Index reloaded",
            "document_count": current_searcher.document_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload: {e}")


# Run with: uvicorn app.main:app --reload
if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run(app, host=host, port=port)

