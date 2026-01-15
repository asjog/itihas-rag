#!/bin/bash
# Script to set up ChromaDB vectors on Render

set -e

VECTORS_DIR="${VECTORS_DIR:-/data/vectors}"

echo "Checking if vectors already exist at $VECTORS_DIR..."

if [ -f "$VECTORS_DIR/chroma.sqlite3" ]; then
    echo "✓ Vectors already exist. Skipping setup."
    exit 0
fi

echo "⚠️ Vectors not found. You have two options:"
echo ""
echo "Option 1: Upload pre-built vectors"
echo "  1. Download vectors from your local machine"
echo "  2. Use Render Shell to upload them to $VECTORS_DIR"
echo ""
echo "Option 2: Regenerate vectors (requires GOOGLE_API_KEY)"
echo "  This will use the Gemini API and may incur costs."
echo ""
echo "To regenerate vectors, set REGENERATE_VECTORS=true in environment"

if [ "$REGENERATE_VECTORS" = "true" ]; then
    echo "Regenerating vectors... This may take 30-60 minutes."
    # Note: This would require copying the embedding generation script
    # from itihas-rag-proc to this repository
    echo "ERROR: Vector regeneration script not included in this deployment."
    echo "Please upload pre-built vectors instead."
    exit 1
else
    echo "Skipping vector regeneration. Semantic search will not work until vectors are uploaded."
fi
