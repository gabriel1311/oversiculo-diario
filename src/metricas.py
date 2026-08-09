"""
Coleta métricas reais do Instagram (curtidas, comentários, alcance, seguidores)
e grava em dados/metricas.json — a página de controle lê daqui.

Defensivo de propósito: cada chamada é isolada. Se o token não tiver permissão
de Insights (alcance/salvos), a gente ainda grava curtidas/comentários e nunca
derruba o processo. Sempre sai com código 0.

    python3 -m src.metricas
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

from src import instagram, versiculos

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "dados" / "metricas.json"
ARQUIVO_HISTORICO = RAIZ / "dados" / "metricas-historico.json"


def _atualizar_historico(dados: dict) -> None:
    """Guarda um snapshot por dia (seguidores + totais) para o relatório de crescimento."""
    posts = dados.get("posts", [])
    def soma(campo):
        vals = [p.get(campo) for p in posts if p.get(campo) is not None]
        return sum(vals) if vals else None
    hoje = dados["atualizado"][:10]
    snapshot = {
        "data": hoje,
        "seguidores": dados.get("seguidores"),
        "posts": len(posts),
        "curtidas": soma("likes"),
        "comentarios": soma("comentarios"),
        "alcance": soma("alcance"),
        "salvos": soma("salvos"),
    }
    historico = []
    if ARQUIVO_HISTORICO.exists():
        historico = json.loads(ARQUIVO_HISTORICO.read_text(encoding="utf-8"))
    historico = [h for h in historico if h.get("data") != hoje]  # 1 por dia
    historico.append(snapshot)
    historico.sort(key=lambda h: h["data"])
    ARQUIVO_HISTORICO.write_text(json.dumps(historico, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _api(caminho: str, campos: dict) -> dict | None:
    try:
        return instagram._get(caminho, campos)
    except instagram.ErroInstagram as erro:
        print(f"[metricas] sem dados de {caminho}: {erro}")
        return None


def coletar() -> dict:
    token = os.environ.get("IG_ACCESS_TOKEN")
    conta = os.environ.get("IG_ACCOUNT_ID")
    if not token or not conta:
        raise RuntimeError("faltam IG_ACCESS_TOKEN e/ou IG_ACCOUNT_ID")

    resultado: dict = {
        "atualizado": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "seguidores": None,
        "posts": [],
    }

    conta_info = _api(conta, {"fields": "followers_count,media_count,username", "access_token": token})
    if conta_info:
        resultado["seguidores"] = conta_info.get("followers_count")
        resultado["media_count"] = conta_info.get("media_count")
        resultado["username"] = conta_info.get("username")
        print(f"[metricas] seguidores: {resultado['seguidores']}")

    for h in versiculos.carregar_historico():
        mid = h.get("id_post")
        if not mid:
            continue
        item = {"data": h["data"], "referencia": h["referencia"], "consulta": h["consulta"], "id": mid}

        basico = _api(mid, {"fields": "like_count,comments_count,permalink,media_type", "access_token": token})
        if basico:
            item["likes"] = basico.get("like_count")
            item["comentarios"] = basico.get("comments_count")
            item["permalink"] = basico.get("permalink")

        # Alcance/salvos dependem de permissão de Insights — opcional.
        insights = _api(f"{mid}/insights", {"metric": "reach,saved", "access_token": token})
        if insights and insights.get("data"):
            for m in insights["data"]:
                if m.get("name") == "reach" and m.get("values"):
                    item["alcance"] = m["values"][0].get("value")
                if m.get("name") == "saved" and m.get("values"):
                    item["salvos"] = m["values"][0].get("value")

        resultado["posts"].append(item)

    return resultado


def main() -> int:
    try:
        dados = coletar()
    except Exception as erro:  # nunca derruba o workflow por causa de métricas
        print(f"::warning::Não consegui coletar métricas: {erro}")
        return 0
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _atualizar_historico(dados)
    print(f"[metricas] gravado {ARQUIVO.name}: {len(dados['posts'])} posts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
