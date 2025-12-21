#!/usr/bin/env python3
"""
Script to copy text files from multiple source folders to the corpus directory,
renaming them to include the parent folder name to avoid conflicts.

Example:
  /source/marathi-riyasat-purvardha/text/page_0000.txt
  → corpus/marathi-riyasat-purvardha_page_0000.txt
"""

import argparse
import shutil
from pathlib import Path


def find_riyasat_folders(base_path: Path) -> list[Path]:
    """Find all folders containing 'riyasat' in their name."""
    riyasat_folders = []
    
    for path in base_path.rglob("*"):
        if path.is_dir() and "riyasat" in path.name.lower():
            # Check if this folder has a 'text' subdirectory or contains .txt files
            text_subdir = path / "text"
            if text_subdir.exists():
                riyasat_folders.append(text_subdir)
            elif list(path.glob("*.txt")):
                riyasat_folders.append(path)
    
    return riyasat_folders


def copy_files(source_folders: list[Path], dest_dir: Path, dry_run: bool = False) -> dict:
    """
    Copy text files from source folders to destination,
    prefixing filenames with the parent folder name.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    stats = {
        "total": 0,
        "copied": 0,
        "skipped": 0,
        "errors": 0
    }
    
    for folder in source_folders:
        # Get the parent folder name (e.g., "marathi-riyasat-purvardha")
        # If we're in a "text" subfolder, go up one level
        if folder.name == "text":
            prefix = folder.parent.name
        else:
            prefix = folder.name
        
        print(f"\nProcessing: {folder}")
        print(f"  Prefix: {prefix}")
        
        txt_files = sorted(folder.glob("*.txt"))
        print(f"  Found {len(txt_files)} text files")
        
        for txt_file in txt_files:
            stats["total"] += 1
            
            # Create new filename: prefix_originalname.txt
            new_name = f"{prefix}_{txt_file.name}"
            dest_path = dest_dir / new_name
            
            if dest_path.exists():
                print(f"  Skipping (exists): {new_name}")
                stats["skipped"] += 1
                continue
            
            try:
                if dry_run:
                    print(f"  Would copy: {txt_file.name} → {new_name}")
                else:
                    shutil.copy2(txt_file, dest_path)
                    if stats["copied"] < 5 or stats["copied"] % 100 == 0:
                        print(f"  Copied: {txt_file.name} → {new_name}")
                stats["copied"] += 1
            except Exception as e:
                print(f"  Error copying {txt_file.name}: {e}")
                stats["errors"] += 1
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Copy text files from riyasat folders to corpus directory"
    )
    parser.add_argument(
        "--source",
        default="/Users/amod/Desktop/tarcaz/zupe-google-cloud/data/processed-data",
        help="Base directory to search for riyasat folders"
    )
    parser.add_argument(
        "--dest",
        default="./corpus",
        help="Destination corpus directory (default: ./corpus)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without actually copying"
    )
    parser.add_argument(
        "--pattern",
        default="riyasat",
        help="Pattern to match in folder names (default: riyasat)"
    )
    
    args = parser.parse_args()
    
    source_path = Path(args.source)
    dest_path = Path(args.dest)
    
    if not source_path.exists():
        print(f"Error: Source path does not exist: {source_path}")
        return 1
    
    print(f"Searching for folders with '{args.pattern}' in: {source_path}")
    
    # Find folders
    riyasat_folders = find_riyasat_folders(source_path)
    
    if not riyasat_folders:
        print(f"No folders with '{args.pattern}' found.")
        return 1
    
    print(f"\nFound {len(riyasat_folders)} folders:")
    for folder in riyasat_folders:
        print(f"  - {folder}")
    
    if args.dry_run:
        print("\n[DRY RUN - no files will be copied]")
    
    # Copy files
    stats = copy_files(riyasat_folders, dest_path, dry_run=args.dry_run)
    
    print(f"\n{'=' * 50}")
    print(f"Summary:")
    print(f"  Total files found: {stats['total']}")
    print(f"  Copied: {stats['copied']}")
    print(f"  Skipped (already exist): {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Destination: {dest_path.absolute()}")
    
    if args.dry_run:
        print("\n[DRY RUN complete - run without --dry-run to copy files]")
    
    return 0


if __name__ == "__main__":
    exit(main())

