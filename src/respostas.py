"""
Responde automaticamente os comentários deixados nos NOSSOS posts.

A Graph API não permite comentar em post alheio, mas responder comentários dos
próprios posts é oficialmente suportado (POST /{comment-id}/replies). Cada
resposta conta como engajamento e mantém a conta "viva" sem intervenção manual.

Regras:
- Só posts recentes (JANELA_DIAS) do histórico — post velho não recebe visita.
- Só comentários de nível superior (respostas a respostas ficam de fora).
- Pula comentários da própria conta, com link (spam) ou já respondidos.
- Resposta escolhida por hash FNV do id do comentário: determinística
  (re-rodar não muda nada) e variada entre comentários.
- Estado em dados/respondidos.json (commitado pelo workflow) — é ele que
  garante a idempotência entre execuções.
- Defensivo como o de métricas: falha de uma chamada não derruba o processo.

    python -m src.respostas            # responde os comentários novos
    python -m src.respostas --teste    # cria, responde e apaga um comentário
                                       # próprio no post mais recente (valida
                                       # as permissões do token de ponta a ponta)
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from src import instagram, versiculos

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "dados" / "respondidos.json"

JANELA_DIAS = 21          # posts mais velhos que isso não são mais vigiados
MAX_POR_EXECUCAO = 15     # teto de respostas por rodada, por segurança

# Pool de respostas — curtas, calorosas e variadas. A escolha por FNV faz
# comentários diferentes receberem respostas diferentes, mas o MESMO comentário
# sempre levar à mesma resposta (idempotente por construção).
RESPOSTAS = [
    "Amém! 🙏 Que essa palavra te acompanhe hoje.",
    "Glória a Deus! 🙌 Obrigado pela presença.",
    "Amém! Deus abençoe o seu dia. ✨",
    "Que alegria te ver por aqui! Deus te abençoe 🙏",
    "Amém! Que a paz de Deus esteja com você. 🕊️",
    "Deus é fiel! 🙌 Obrigado pelo carinho.",
    "Amém! Que essa promessa se cumpra na sua vida. 🙏",
    "Toda honra a Ele! 🙌 Volte sempre.",
    "Amém! 🙏 Tem versículo novo todo dia, te espero amanhã.",
    "Deus te abençoe grandemente! ✨",
    "Que Ele renove as suas forças hoje. Amém! 🙏",
    "Amém! Compartilhe com alguém que precisa dessa palavra. 💛",
]


def _fnv(texto: str) -> int:
    """FNV-1a 32 bits — mesmo hash portável usado no resto do projeto."""
    h = 2166136261
    for byte in texto.encode("utf-8"):
        h = ((h ^ byte) * 16777619) & 0xFFFFFFFF
    return h


def _delete(caminho: str, campos: dict[str, str]) -> dict:
    url = f"{instagram.BASE}/{caminho}?" + urllib.parse.urlencode(campos)
    requisicao = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(requisicao, timeout=60) as resposta:
        return json.load(resposta)


def _carregar_respondidos() -> dict:
    if ARQUIVO.exists():
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    return {}


def _salvar_respondidos(respondidos: dict) -> None:
    ARQUIVO.write_text(
        json.dumps(respondidos, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _posts_recentes() -> list[dict]:
    hoje = datetime.date.today()
    recentes = []
    for h in versiculos.carregar_historico():
        if not h.get("id_post"):
            continue
        idade = (hoje - datetime.date.fromisoformat(h["data"])).days
        if idade <= JANELA_DIAS:
            recentes.append(h)
    return recentes


def _comentarios(mid: str, token: str) -> list[dict]:
    dados = instagram._get(
        f"{mid}/comments",
        {"fields": "id,text,username,timestamp", "limit": "50", "access_token": token},
    )
    return dados.get("data", [])


def responder_novos() -> int:
    token = os.environ.get("IG_ACCESS_TOKEN")
    conta = os.environ.get("IG_ACCOUNT_ID")
    if not token or not conta:
        raise RuntimeError("faltam IG_ACCESS_TOKEN e/ou IG_ACCOUNT_ID")

    info = instagram._get(conta, {"fields": "username", "access_token": token})
    proprio = (info.get("username") or "").lower()

    respondidos = _carregar_respondidos()
    enviadas = 0

    for post in _posts_recentes():
        mid = post["id_post"]
        try:
            comentarios = _comentarios(mid, token)
        except instagram.ErroInstagram as erro:
            print(f"[respostas] pulei {post['referencia']}: {erro}")
            continue

        if comentarios:
            print(f"[respostas] {post['referencia']}: {len(comentarios)} comentário(s) na API")
        for c in comentarios:
            cid = c.get("id")
            texto = (c.get("text") or "").strip()
            autor = (c.get("username") or "").lower()
            if not cid or cid in respondidos:
                continue
            if autor == proprio:
                continue  # nosso próprio comentário (ou resposta antiga)
            if "http" in texto.lower():
                print(f"[respostas] ignorei @{autor} (link no texto)")
                respondidos[cid] = {"ignorado": "link", "autor": autor}
                continue
            if enviadas >= MAX_POR_EXECUCAO:
                print(f"[respostas] teto de {MAX_POR_EXECUCAO} atingido; o resto fica para a próxima rodada")
                break

            mensagem = RESPOSTAS[_fnv(cid) % len(RESPOSTAS)]
            try:
                criada = instagram._post(f"{cid}/replies", {"message": mensagem, "access_token": token})
            except instagram.ErroInstagram as erro:
                print(f"[respostas] falhou responder @{autor}: {erro}")
                continue
            respondidos[cid] = {
                "autor": autor,
                "post": post["referencia"],
                "resposta": mensagem,
                "id_resposta": criada.get("id"),
                "quando": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            }
            enviadas += 1
            print(f"[respostas] @{autor} em {post['referencia']} → “{mensagem}”")

    _salvar_respondidos(respondidos)
    print(f"[respostas] {enviadas} resposta(s) enviada(s); {len(respondidos)} no total")
    return 0


def teste_ponta_a_ponta() -> int:
    """
    Valida as permissões do token sem esperar um comentário real: comenta no
    post mais recente, responde o próprio comentário e apaga os dois. Se as
    três chamadas passam, o fluxo real está garantido.
    """
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("falta IG_ACCESS_TOKEN")
    recentes = _posts_recentes()
    if not recentes:
        print("[teste] nenhum post recente no histórico")
        return 1
    mid = recentes[-1]["id_post"]

    criado = instagram._post(f"{mid}/comments", {"message": "Teste da automação 🙏 (já apago)", "access_token": token})
    cid = criado.get("id")
    print(f"[teste] comentário criado: {cid}")

    resposta = instagram._post(f"{cid}/replies", {"message": "Resposta de teste 🙌", "access_token": token})
    rid = resposta.get("id")
    print(f"[teste] resposta criada: {rid}")

    for alvo in (rid, cid):
        if alvo:
            _delete(alvo, {"access_token": token})
            print(f"[teste] apagado: {alvo}")

    print("[teste] permissões OK — criar, responder e apagar funcionaram")
    return 0


def main() -> int:
    try:
        if "--teste" in sys.argv:
            return teste_ponta_a_ponta()
        return responder_novos()
    except Exception as erro:  # nunca derruba o workflow: melhor responder amanhã que alarmar hoje
        print(f"::warning::Respostas automáticas falharam: {erro}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
