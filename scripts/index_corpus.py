#!/usr/bin/env python3
"""
Corpus indexing script for Marathi text search.

This script reads text files from the corpus directory and creates
a Xapian search index with multi-variant text indexing for OCR robustness.

Usage:
    python scripts/index_corpus.py [--corpus-dir ./corpus] [--index-dir ./indexes]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import xapian

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.normalize import MarathiNormalizer, get_normalizer


# Slot numbers for document values (used for sorting/filtering)
SLOT_FILE_PATH = 0
SLOT_PAGE_NUMBER = 1


def extract_page_number(file_path: Path) -> int | None:
    """
    Extract page number from filename.
    
    Expects filenames like:
    - page_001.txt
    - 001.txt
    - book_page_42.txt
    
    Args:
        file_path: Path to the text file
        
    Returns:
        Page number or None if not found
    """
    filename = file_path.stem  # Get filename without extension
    
    # Try to find a number in the filename
    numbers = re.findall(r'\d+', filename)
    if numbers:
        # Take the last number (most likely to be the page number)
        return int(numbers[-1])
    
    return None


def index_document(
    indexer: xapian.TermGenerator,
    db: xapian.WritableDatabase,
    file_path: Path,
    normalizer: MarathiNormalizer,
    doc_id: int
) -> bool:
    """
    Index a single document.
    
    Args:
        indexer: Xapian TermGenerator
        db: Xapian database
        file_path: Path to the text file
        normalizer: MarathiNormalizer instance
        doc_id: Document ID for tracking
        
    Returns:
        True if indexing was successful
    """
    try:
        # Read the file content
        content = file_path.read_text(encoding='utf-8')
        
        if not content.strip():
            print(f"  Skipping empty file: {file_path}")
            return False
        
        # Extract page number from filename
        page_num = extract_page_number(file_path)
        
        # Create a new Xapian document
        doc = xapian.Document()
        
        # Set up the term generator for this document
        indexer.set_document(doc)
        
        # Index multiple variants for OCR robustness
        variants = normalizer.get_variants(content)
        for i, variant in enumerate(variants):
            # Index with different weight prefixes for variants
            # Original text gets higher weight
            weight = 1 if i == 0 else 2
            indexer.index_text(variant, weight)
        
        # Store metadata as JSON in document data
        metadata = {
            "file_path": str(file_path),
            "page_number": page_num,
            "content": content,  # Store full content for display
            "content_preview": content[:500] if len(content) > 500 else content,
            "char_count": len(content),
            "doc_id": doc_id
        }
        doc.set_data(json.dumps(metadata, ensure_ascii=False))
        
        # Store values for sorting/filtering
        doc.add_value(SLOT_FILE_PATH, str(file_path))
        if page_num is not None:
            doc.add_value(SLOT_PAGE_NUMBER, xapian.sortable_serialise(page_num))
        
        # Add the document to the database
        db.add_document(doc)
        
        return True
        
    except Exception as e:
        print(f"  Error indexing {file_path}: {e}")
        return False


def index_corpus(corpus_dir: str, index_dir: str, force_rebuild: bool = False) -> dict:
    """
    Index all text files in the corpus directory.
    
    Args:
        corpus_dir: Path to directory containing text files
        index_dir: Path to directory for Xapian index
        force_rebuild: If True, delete existing index and rebuild
        
    Returns:
        Dictionary with indexing statistics
    """
    corpus_path = Path(corpus_dir)
    index_path = Path(index_dir)
    
    # Validate corpus directory
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_path}")
    
    # Get list of text files
    text_files = sorted(corpus_path.glob("*.txt"))
    
    if not text_files:
        print(f"No .txt files found in {corpus_path}")
        return {"total": 0, "indexed": 0, "skipped": 0, "errors": 0}
    
    print(f"Found {len(text_files)} text files in {corpus_path}")
    
    # Create index directory if it doesn't exist
    index_path.mkdir(parents=True, exist_ok=True)
    
    # Handle existing index
    xapian_db_path = index_path / "xapian_db"
    if xapian_db_path.exists():
        if force_rebuild:
            import shutil
            print(f"Removing existing index at {xapian_db_path}")
            shutil.rmtree(xapian_db_path)
        else:
            print(f"Index already exists at {xapian_db_path}")
            print("Use --force to rebuild the index")
    
    # Create/open the Xapian database
    db = xapian.WritableDatabase(str(xapian_db_path), xapian.DB_CREATE_OR_OPEN)
    
    # Set up the term generator
    indexer = xapian.TermGenerator()
    # Don't use stemming for Marathi - it doesn't have good support
    indexer.set_stemmer(xapian.Stem("none"))
    
    # Get the normalizer
    normalizer = get_normalizer()
    
    # Statistics
    stats = {
        "total": len(text_files),
        "indexed": 0,
        "skipped": 0,
        "errors": 0
    }
    
    print("\nIndexing documents...")
    
    for i, file_path in enumerate(text_files):
        if (i + 1) % 100 == 0 or i == 0:
            print(f"  Processing {i + 1}/{len(text_files)}: {file_path.name}")
        
        success = index_document(indexer, db, file_path, normalizer, i)
        
        if success:
            stats["indexed"] += 1
        else:
            stats["skipped"] += 1
    
    # Commit changes
    db.commit()
    
    # Get final document count
    stats["db_doc_count"] = db.get_doccount()
    
    print(f"\nIndexing complete!")
    print(f"  Total files: {stats['total']}")
    print(f"  Indexed: {stats['indexed']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"  Documents in database: {stats['db_doc_count']}")
    
    return stats


def main():
    """Main entry point for the indexing script."""
    parser = argparse.ArgumentParser(
        description="Index Marathi text corpus for search"
    )
    parser.add_argument(
        "--corpus-dir",
        default="./corpus",
        help="Directory containing text files (default: ./corpus)"
    )
    parser.add_argument(
        "--index-dir",
        default="./indexes",
        help="Directory for Xapian index (default: ./indexes)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild of existing index"
    )
    
    args = parser.parse_args()
    
    try:
        stats = index_corpus(args.corpus_dir, args.index_dir, args.force)
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

