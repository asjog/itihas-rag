# मराठी शोध (Marathi Text Search)

A fast and robust text search engine for Marathi text corpus, featuring keyword search with OCR error tolerance.

## Features

- **Xapian-powered search**: Fast full-text search using Xapian search engine
- **RapidFuzz reranking**: Fuzzy matching to handle OCR errors in scanned documents
- **Unicode/Indic normalization**: Consistent handling of Devanagari text variations
- **Multi-variant indexing**: Indexes multiple normalized forms for better recall
- **REST API**: FastAPI-based API with automatic documentation
- **Modern UI**: Clean, responsive frontend with Devanagari support

## Tech Stack

| Layer | Technology |
|-------|------------|
| Core Search Engine | Xapian (Python bindings) |
| OCR Robustness | RapidFuzz |
| Text Normalization | Custom Unicode + Indic NLP pipeline |
| Backend | FastAPI + Uvicorn |
| Frontend | Vanilla HTML/CSS/JS |

## Quick Start

### Prerequisites

- Python 3.10+
- Xapian (installed via Homebrew on macOS: `brew install xapian`)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd itihas-rag
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Add your corpus**
   
   Place your text files (one page per file) in the `corpus/` directory:
   ```
   corpus/
   ├── page_001.txt
   ├── page_002.txt
   └── ...
   ```

5. **Index the corpus**
   ```bash
   python scripts/index_corpus.py
   ```

6. **Run the server**
   ```bash
   uvicorn app.main:app --reload
   ```

7. **Open the app**
   
   Visit http://localhost:8000 in your browser.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Frontend UI |
| `/api/health` | GET | Health check |
| `/api/search` | GET | Keyword search |
| `/api/search/exact` | GET | Exact phrase search |
| `/api/reload` | GET | Reload search index |
| `/docs` | GET | API documentation (Swagger) |

### Search API

```bash
# Keyword search
curl "http://localhost:8000/api/search?query=शिवाजी महाराज&limit=10"

# Exact phrase search
curl "http://localhost:8000/api/search/exact?query=मराठी भाषा"

# Disable fuzzy matching
curl "http://localhost:8000/api/search?query=पुणे&fuzzy=false"
```

## Deployment

### Docker

```bash
docker build -t itihas-rag .
docker run -p 8000:8000 -v ./corpus:/app/corpus -v ./indexes:/app/indexes itihas-rag
```

### Render.com

1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Select "Docker" as the environment
4. Deploy!

The `render.yaml` file is included for easy deployment.

## Project Structure

```
itihas-rag/
├── app/
│   ├── main.py              # FastAPI application
│   ├── search/
│   │   └── keyword.py       # Xapian + RapidFuzz search
│   ├── utils/
│   │   └── normalize.py     # Unicode/Indic normalization
│   └── models/
│       └── search.py        # Pydantic models
├── scripts/
│   └── index_corpus.py      # Corpus indexer
├── corpus/                  # Text files (add your own)
├── indexes/                 # Xapian index (auto-generated)
├── frontend/
│   └── index.html           # Web UI
├── Dockerfile
├── render.yaml
├── requirements.txt
└── README.md
```

## Configuration

Environment variables (optional):

| Variable | Default | Description |
|----------|---------|-------------|
| `CORPUS_DIR` | `./corpus` | Path to corpus directory |
| `INDEX_DIR` | `./indexes` | Path to index directory |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |
| `DEFAULT_RESULT_LIMIT` | `20` | Default search result limit |

## Development

```bash
# Run with auto-reload
uvicorn app.main:app --reload

# Re-index corpus
python scripts/index_corpus.py --force

# Run tests
python -m pytest tests/
```

## Phase 2: Semantic Search (Coming Soon)

- Multilingual embeddings using `intfloat/multilingual-e5-base`
- Vector database (ChromaDB or Qdrant)
- Combined keyword + semantic search

## License

MIT License

