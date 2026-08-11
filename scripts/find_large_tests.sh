#!/usr/bin/env bash

THRESHOLD=750

echo "=== Individual Test Files > $THRESHOLD LOC ==="
find tests -type f \( -name "test_*.py" -o -name "*_test.py" \) -exec wc -l {} + \
  | awk -v threshold="$THRESHOLD" '$1 > threshold && $2 != "total" {printf "%-6d %s\n", $1, $2}' \
  | sort -nr

echo ""
echo "=== Test Subdirectories/Modules > $THRESHOLD LOC ==="
find tests -mindepth 1 -type d | while read -r dir; do
  total_loc=$(find "$dir" -maxdepth 1 -type f \( -name "test_*.py" -o -name "*_test.py" \) -exec wc -l {} + 2>/dev/null | awk 'END {print $1}')
  if [ -n "$total_loc" ] && [ "$total_loc" -gt "$THRESHOLD" ]; then
    printf "%-6d %s\n" "$total_loc" "$dir"
  fi
done | sort -nr
