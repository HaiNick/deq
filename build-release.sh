#!/bin/bash
# Build DeQ release ZIP

VERSION=$(grep -o 'VERSION = "[^"]*"' server.py | cut -d'"' -f2)
RELEASE_DIR="deq-release"
ZIP_NAME="deq.zip"

echo "Building DeQ release v${VERSION}..."

# Clean up
rm -rf "$RELEASE_DIR" "$ZIP_NAME"

# Create release directory
mkdir -p "$RELEASE_DIR/fonts"

# Copy files
cp server.py "$RELEASE_DIR/"
cp install.sh "$RELEASE_DIR/"
cp LICENSE "$RELEASE_DIR/"
cp README.md "$RELEASE_DIR/"

# Copy fonts
cp fonts/*.woff2 "$RELEASE_DIR/fonts/" 2>/dev/null

# Check if fonts exist
if [ ! -f "$RELEASE_DIR/fonts/JetBrainsMono-Regular.woff2" ]; then
    echo "Warning: Fonts not found in fonts/ directory"
    echo "Download from: https://www.jetbrains.com/mono/"
fi

# Create ZIP
cd "$RELEASE_DIR"
zip -r "../$ZIP_NAME" .
cd ..

# Clean up
rm -rf "$RELEASE_DIR"

echo ""
echo "Created: $ZIP_NAME"
echo "Size: $(du -h $ZIP_NAME | cut -f1)"
echo ""
echo "Upload this file to GitHub Releases."
