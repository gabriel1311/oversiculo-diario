#!/usr/bin/env bash
#
# Troca o código de autorização do Instagram por um token de longa duração
# (60 dias), em duas etapas — código → token curto → token longo.
#
# Uso:
#   IG_APP_SECRET=xxxxx ./ferramentas/trocar_token.sh <código>
#
# O segredo vai por variável de ambiente para não ficar no histórico do shell.
# Pegue-o no painel: seção "Configuração da API com login do Instagram",
# campo "Chave secreta do app do Instagram", botão "Mostrar".

set -euo pipefail

APP_ID="1679657233107144"
REDIRECT="https://localhost:8443/callback"

CODE="${1:-}"
if [[ -z "$CODE" ]]; then
  echo "Faltou o código. Uso: IG_APP_SECRET=xxx $0 <código>" >&2
  exit 1
fi
if [[ -z "${IG_APP_SECRET:-}" ]]; then
  echo "Faltou IG_APP_SECRET no ambiente." >&2
  exit 1
fi

# O Instagram às vezes anexa "#_" ao fim do código na barra de endereço.
CODE="${CODE%%#*}"

echo "1/2 — trocando o código por um token curto..." >&2
CURTO_JSON="$(curl -sS -X POST https://api.instagram.com/oauth/access_token \
  -F "client_id=${APP_ID}" \
  -F "client_secret=${IG_APP_SECRET}" \
  -F "grant_type=authorization_code" \
  -F "redirect_uri=${REDIRECT}" \
  -F "code=${CODE}")"

# Extrai o campo access_token sem depender de jq.
TOKEN_CURTO="$(printf '%s' "$CURTO_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])' 2>/dev/null || true)"
if [[ -z "$TOKEN_CURTO" ]]; then
  echo "Falhou na etapa 1. Resposta do Instagram:" >&2
  echo "$CURTO_JSON" >&2
  exit 1
fi

echo "2/2 — trocando por um token de 60 dias..." >&2
LONGO_JSON="$(curl -sS -G https://graph.instagram.com/access_token \
  --data-urlencode "grant_type=ig_exchange_token" \
  --data-urlencode "client_secret=${IG_APP_SECRET}" \
  --data-urlencode "access_token=${TOKEN_CURTO}")"

TOKEN_LONGO="$(printf '%s' "$LONGO_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])' 2>/dev/null || true)"
if [[ -z "$TOKEN_LONGO" ]]; then
  echo "Falhou na etapa 2. Resposta do Instagram:" >&2
  echo "$LONGO_JSON" >&2
  exit 1
fi

echo >&2
echo "Pronto. Seu token de longa duração (vale 60 dias):" >&2
echo "$TOKEN_LONGO"
echo >&2
echo "Cadastre com:  gh secret set IG_ACCESS_TOKEN" >&2
echo "(cole o token acima quando pedir; ele não fica gravado em arquivo nenhum)" >&2
