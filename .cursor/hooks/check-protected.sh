#!/bin/bash
# Запрещает агенту Cursor менять защищённые и генерируемые файлы.
# Список синхронизирован с .cursor/rules/agent-boundaries.mdc.

input=$(cat)
path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.path // .tool_input.target_file // empty')
root=$(printf '%s' "$input" | jq -r '.workspace_roots[0] // .cwd // empty')

[ -z "$path" ] && { echo '{"permission": "allow"}'; exit 0; }

rel="${path#"$root"/}"
rel="${rel#./}"

deny() {
  printf '{"permission": "deny", "user_message": "Файл %s защищён правилами Panamaster.", "agent_message": "%s: %s. Предложи изменение текстом в ответе."}\n' "$rel" "$rel" "$1"
  exit 0
}

case "$rel" in
  .cursor/*|.cursorignore|.backup/*|.github/workflows/*|.htaccess|robots.txt)
    deny "защищённый файл, меняет только человек" ;;
  bot/queue/*|bot/logs/*|bot/state/*|bot/dictionaries/*|bot/config.php)
    deny "данные бота, не редактировать" ;;
  cases/*.html|services/*.html|all-services.html|cases.html|cases-[0-9]*.html|sitemap.xml|llms.txt|assets/data/cases.json)
    deny "генерируемый файл, правь шаблон в assets/templates/ или скрипт в bot/" ;;
esac

echo '{"permission": "allow"}'
