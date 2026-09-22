#!/bin/bash

input_data=$(cat)
path=$(echo "$input_data" | jq -r '.tool_input.file_path // empty')

protected=(
  "bot/queue"
  "bot/logs"
  "bot/state"
  "bot/backups"
  "bot/dictionaries"
  ".cursor/rules"
  ".cursor/hooks"
  ".cursorignore"
  "index.html"
  "assets/css/main.css"
  "robots.txt"
  "sitemap.xml"
  "llms.txt"
)

for p in "${protected[@]}"; do
  if [[ "$path" == *"$p"* ]]; then
    echo "{\"permission\": \"deny\", \"user_message\": \"Изменение $path запрещено правилами Panamaster.\"}"
    exit 0
  fi
done

echo "{\"permission\": \"allow\"}"
