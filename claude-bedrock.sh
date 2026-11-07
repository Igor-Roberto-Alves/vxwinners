#!/usr/bin/env bash
# Inicia o Claude Code usando o AWS Bedrock com as credenciais do .env
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a; source "$DIR/.env"; set +a
export AWS_REGION="${AWS_REGION:-$AWS_DEFAULT_REGION}"
export CLAUDE_CODE_USE_BEDROCK=1
exec claude "$@"
