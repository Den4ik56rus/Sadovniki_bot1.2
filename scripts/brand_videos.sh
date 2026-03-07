#!/bin/bash
# Brand flagship videos with PRO Растения logo
# Replaces NotebookLM watermark with our logo
#
# Usage: ./scripts/brand_videos.sh [--dry-run]

set -euo pipefail

LOGO="/Users/denis/Downloads/Telegram Desktop/IMG_1971.PNG"
SOURCE_DIR="/Users/denis/Desktop/Видео бот"

# Verify logo exists
if [ ! -f "$LOGO" ]; then
    echo "ERROR: Logo not found at: $LOGO"
    exit 1
fi

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=true
    echo "=== DRY RUN MODE ==="
    echo
fi

# Folders to process (Клуб лет already branded)
FOLDERS=("Клуб рем" "Малина лет" "Малина рем")

TOTAL=0
DONE=0
FAILED=0

# Count total files
for folder in "${FOLDERS[@]}"; do
    dir="$SOURCE_DIR/$folder"
    if [ -d "$dir" ]; then
        count=$(find "$dir" -maxdepth 1 -name "*.mp4" ! -name "*_branded.mp4" | wc -l | tr -d ' ')
        TOTAL=$((TOTAL + count))
    fi
done

echo "Logo: $LOGO"
echo "Source: $SOURCE_DIR"
echo "Videos to process: $TOTAL"
echo "Folders: ${FOLDERS[*]}"
echo "================================"
echo

for folder in "${FOLDERS[@]}"; do
    dir="$SOURCE_DIR/$folder"
    if [ ! -d "$dir" ]; then
        echo "SKIP: $dir not found"
        continue
    fi

    echo "=== $folder ==="

    for input in "$dir"/*.mp4; do
        # Skip already branded files
        if [[ "$input" == *_branded.mp4 ]]; then
            continue
        fi

        filename=$(basename "$input" .mp4)
        output="$dir/${filename}_branded.mp4"

        if [ -f "$output" ]; then
            echo "  SKIP (exists): $filename"
            DONE=$((DONE + 1))
            continue
        fi

        echo "  PROCESSING: $filename"
        DONE=$((DONE + 1))

        if [ "$DRY_RUN" = true ]; then
            echo "    -> Would create: ${filename}_branded.mp4"
            continue
        fi

        if ffmpeg -y -i "$input" -i "$LOGO" \
            -filter_complex "\
                [1:v]scale=167:-1[logo];\
                [0:v]drawbox=x=1105:y=661:w=167:h=19:color=white@1:t=fill[bg];\
                [bg][logo]overlay=1105:661-h+19" \
            -c:a copy -c:v libx264 -crf 18 -preset medium \
            "$output" 2>/dev/null; then
            size_in=$(du -h "$input" | cut -f1)
            size_out=$(du -h "$output" | cut -f1)
            echo "    OK: $size_in -> $size_out"
        else
            echo "    FAILED: $filename"
            FAILED=$((FAILED + 1))
        fi
    done

    echo
done

echo "================================"
echo "Done: $DONE / $TOTAL"
if [ $FAILED -gt 0 ]; then
    echo "Failed: $FAILED"
fi
