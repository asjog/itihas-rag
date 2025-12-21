"""
Context extraction utilities for search results.

Provides functionality to extract surrounding context (lines before/after)
around search matches, including spanning across adjacent files.
"""

import re
from pathlib import Path
from typing import Optional


CORPUS_DIR = Path(__file__).parent.parent.parent / "corpus"


def parse_filename(filename: str) -> tuple[str, int] | None:
    """
    Parse a corpus filename to extract book name and page number.
    
    Args:
        filename: Filename like "marathi-riyasat-purvardha_page_0001.txt"
        
    Returns:
        Tuple of (book_prefix, page_number) or None if parsing fails
    """
    match = re.match(r'^(.+)_page_(\d+)\.txt$', filename)
    if match:
        return match.group(1), int(match.group(2))
    return None


def get_adjacent_filename(filename: str, offset: int) -> str | None:
    """
    Get the filename for an adjacent page.
    
    Args:
        filename: Current filename
        offset: Page offset (+1 for next, -1 for previous)
        
    Returns:
        Adjacent filename or None if can't determine
    """
    parsed = parse_filename(filename)
    if not parsed:
        return None
    
    book_prefix, page_num = parsed
    new_page = page_num + offset
    
    if new_page < 0:
        return None
    
    return f"{book_prefix}_page_{new_page:04d}.txt"


def read_file_lines(filepath: Path) -> list[str]:
    """Read a file and return its lines."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read().splitlines()
    except (FileNotFoundError, IOError):
        return []


def find_match_line(lines: list[str], query_terms: list[str]) -> int | None:
    """
    Find the first line containing any of the query terms.
    
    Args:
        lines: List of text lines
        query_terms: Terms to search for
        
    Returns:
        Line index or None if not found
    """
    for i, line in enumerate(lines):
        for term in query_terms:
            if term.lower() in line.lower():
                return i
    return None


def extract_context(
    filename: str,
    query: str,
    context_lines: int = 5,
    corpus_dir: Path = CORPUS_DIR
) -> dict:
    """
    Extract context around a search match with lines before and after.
    
    If the file doesn't have enough lines, fetches from adjacent files.
    
    Args:
        filename: The matched file's name
        query: Search query to find the matching line
        context_lines: Number of lines before/after to include (default 5)
        corpus_dir: Path to corpus directory
        
    Returns:
        Dictionary with context information:
        - content: The full context text
        - match_line: The line number where match was found
        - sources: List of source files contributing to the context
        - lines_before: Lines included before match
        - lines_after: Lines included after match
    """
    filepath = corpus_dir / filename
    current_lines = read_file_lines(filepath)
    
    if not current_lines:
        return {
            "content": "",
            "match_line": None,
            "sources": [filename],
            "lines_before": 0,
            "lines_after": 0
        }
    
    # Parse query into terms
    query_terms = [t.strip() for t in query.split() if len(t.strip()) >= 2]
    if not query_terms:
        query_terms = [query]
    
    # Find the matching line
    match_idx = find_match_line(current_lines, query_terms)
    
    if match_idx is None:
        # If no match found, return the whole file
        return {
            "content": "\n".join(current_lines),
            "match_line": 0,
            "sources": [filename],
            "lines_before": 0,
            "lines_after": len(current_lines) - 1
        }
    
    # Calculate how many lines we need from before/after
    lines_needed_before = context_lines
    lines_needed_after = context_lines
    
    # Lines available in current file
    lines_available_before = match_idx
    lines_available_after = len(current_lines) - match_idx - 1
    
    # Collect context
    context_parts = []
    sources = []
    
    # === BEFORE CONTEXT ===
    if lines_available_before < lines_needed_before:
        # Need lines from previous file(s)
        lines_still_needed = lines_needed_before - lines_available_before
        prev_filename = get_adjacent_filename(filename, -1)
        
        if prev_filename:
            prev_path = corpus_dir / prev_filename
            prev_lines = read_file_lines(prev_path)
            
            if prev_lines:
                # Take last N lines from previous file
                prev_context = prev_lines[-lines_still_needed:]
                if prev_context:
                    context_parts.append(f"[← {prev_filename}]")
                    context_parts.extend(prev_context)
                    context_parts.append("---")
                    sources.append(prev_filename)
    
    # Add lines from current file before match
    start_idx = max(0, match_idx - context_lines)
    before_lines = current_lines[start_idx:match_idx]
    context_parts.extend(before_lines)
    
    # === MATCH LINE ===
    context_parts.append(current_lines[match_idx])
    sources.append(filename)
    
    # === AFTER CONTEXT ===
    end_idx = min(len(current_lines), match_idx + context_lines + 1)
    after_lines = current_lines[match_idx + 1:end_idx]
    context_parts.extend(after_lines)
    
    if lines_available_after < lines_needed_after:
        # Need lines from next file(s)
        lines_still_needed = lines_needed_after - lines_available_after
        next_filename = get_adjacent_filename(filename, +1)
        
        if next_filename:
            next_path = corpus_dir / next_filename
            next_lines = read_file_lines(next_path)
            
            if next_lines:
                # Take first N lines from next file
                next_context = next_lines[:lines_still_needed]
                if next_context:
                    context_parts.append("---")
                    context_parts.append(f"[→ {next_filename}]")
                    context_parts.extend(next_context)
                    sources.append(next_filename)
    
    return {
        "content": "\n".join(context_parts),
        "match_line": match_idx,
        "sources": sources,
        "lines_before": len(before_lines) + (len(context_parts) - len(before_lines) - len(after_lines) - 1),
        "lines_after": len(after_lines) + (len([p for p in context_parts if p.startswith("[→")]))
    }


def extract_context_simple(
    content: str,
    query: str,
    context_lines: int = 5
) -> str:
    """
    Extract context from content string without file access.
    
    Args:
        content: Full text content
        query: Search query
        context_lines: Lines of context before/after
        
    Returns:
        Context string
    """
    lines = content.splitlines()
    query_terms = [t.strip() for t in query.split() if len(t.strip()) >= 2]
    if not query_terms:
        query_terms = [query]
    
    match_idx = find_match_line(lines, query_terms)
    
    if match_idx is None:
        # Return first portion of content
        return "\n".join(lines[:context_lines * 2 + 1])
    
    start = max(0, match_idx - context_lines)
    end = min(len(lines), match_idx + context_lines + 1)
    
    return "\n".join(lines[start:end])

