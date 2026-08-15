"""
A inteligência do projeto: aprende com as métricas e decide os próximos posts.

Aprende cruzando dados/historico.json (características de cada post: estilo,
hora, tamanho do versículo) com dados/metricas.json (curtidas, comentários,
alcance, salvos). O resultado vira dados/inteligencia.json — pesos que as
outras partes do sistema usam para decidir:

  - imagem.escolher_estilo  → qual estilo visual usar no dia
  - versiculos.escolher     → preferir versículos do tamanho que rende mais
  - workflow publicar       → a que horas publicar (8h, 12h ou 19h)

Princípios:
  - Score de um post = curtidas + 3×comentários + 5×salvos (o que o algoritmo
    do Instagram valoriza pesa mais).
  - Suavização bayesiana: com poucos dados, os pesos ficam perto da média —
    nada de conclusões precipitadas com 3 posts.
  - Piso de exploração: nenhuma opção zera; o sistema sempre testa um pouco de
    tudo para continuar aprendendo (e a escolha diária é determinística pela
    data, então um retry no mesmo dia decide igual).

Módulo 100%% stdlib de propósito: o "gate" de horário no workflow roda antes
do pip install.

    python3 -m src.inteligencia          # aprende e grava dados/inteligencia.json
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ_HISTORICO = RAIZ / "dados" / "historico.json"
ARQ_METRICAS = RAIZ / "dados" / "metricas.json"
ARQ_POOL = RAIZ / "dados" / "versiculos.json"
ARQ_SAIDA = RAIZ / "dados" / "inteligencia.json"

PESO_CURTIDA, PESO_COMENTARIO, PESO_SALVO = 1, 3, 5
SUAVIZACAO = 3  # pseudo-amostras puxando cada opção para a média global

ESTILOS = ["classico", "bilhete", "livro", "foto"]
TAMANHOS = ["curto", "medio", "longo"]     # ≤100 / 101–180 / >180 caracteres
HORAS = [8, 12, 19]                        # horários candidatos (Brasília)

# Pisos de exploração (%). A bio promete "às 8h", então as 8h têm piso maior —
# os outros horários são testados aos poucos; se um deles vencer com folga,
# vale atualizar a bio junto.
# Gabriel gosta do estilo foto (paisagem) — piso maior garante presença
# constante na rotação mesmo enquanto as métricas ainda não o favorecem.
PISO_ESTILO = {"classico": 12, "bilhete": 12, "livro": 12, "foto": 35}
PISO_TAMANHO = 15
PISO_HORA = {8: 40, 12: 15, 19: 15}


def _fnv(texto: str) -> int:
    h = 2166136261
    for ch in texto:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _ler(caminho: Path, padrao):
    if not caminho.exists():
        return padrao
    return json.loads(caminho.read_text(encoding="utf-8"))


def _bucket(n_chars: int) -> str:
    if n_chars <= 100:
        return "curto"
    if n_chars <= 180:
        return "medio"
    return "longo"


def _pesos(observacoes: dict[str, list[float]], opcoes: list, piso) -> dict:
    """Média suavizada por opção → pesos inteiros (%), com piso de exploração."""
    todas = [s for scores in observacoes.values() for s in scores]
    media_global = sum(todas) / len(todas) if todas else 1.0
    bruto = {}
    for op in opcoes:
        scores = observacoes.get(str(op), [])
        bruto[str(op)] = (sum(scores) + media_global * SUAVIZACAO) / (len(scores) + SUAVIZACAO)
    soma = sum(bruto.values()) or 1.0
    pesos = {}
    for op in opcoes:
        piso_op = piso[op] if isinstance(piso, dict) else piso
        pesos[str(op)] = max(piso_op, round(bruto[str(op)] / soma * 100))
    # renormaliza para somar 100
    soma_p = sum(pesos.values())
    pesos = {k: max(1, round(v / soma_p * 100)) for k, v in pesos.items()}
    diferenca = 100 - sum(pesos.values())
    primeiro = str(opcoes[0])
    pesos[primeiro] += diferenca
    return pesos


def aprender() -> dict:
    historico = _ler(ARQ_HISTORICO, [])
    metricas = _ler(ARQ_METRICAS, {})
    pool = {v["consulta"]: v["texto"] for v in _ler(ARQ_POOL, [])}
    por_data = {p["data"]: p for p in metricas.get("posts", [])}

    # Só posts com pelo menos ~20h de vida entram na análise: um post recém
    # publicado ainda está somando engajamento e distorceria a comparação.
    ontem = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    obs_estilo: dict[str, list] = {}
    obs_tamanho: dict[str, list] = {}
    obs_hora: dict[str, list] = {}
    ranking = []

    for reg in historico:
        m = por_data.get(reg["data"])
        if not m or reg["data"] > ontem:
            continue
        score = (
            PESO_CURTIDA * (m.get("likes") or 0)
            + PESO_COMENTARIO * (m.get("comentarios") or 0)
            + PESO_SALVO * (m.get("salvos") or 0)
        )
        ranking.append({
            "data": reg["data"], "referencia": reg["referencia"], "score": score,
            "estilo": reg.get("estilo"), "hora": reg.get("hora"),
            "alcance": m.get("alcance"),
        })
        if reg.get("estilo") in ESTILOS:
            obs_estilo.setdefault(reg["estilo"], []).append(score)
        texto = pool.get(reg["consulta"], "")
        if texto:
            obs_tamanho.setdefault(_bucket(len(texto)), []).append(score)
        if reg.get("hora") in HORAS:
            obs_hora.setdefault(str(reg["hora"]), []).append(score)

    ranking.sort(key=lambda r: -r["score"])
    return {
        "atualizado": datetime.date.today().isoformat(),
        "amostras": len(ranking),
        "pesos_estilo": _pesos(obs_estilo, ESTILOS, PISO_ESTILO),
        "pesos_tamanho": _pesos(obs_tamanho, TAMANHOS, PISO_TAMANHO),
        "pesos_hora": _pesos(obs_hora, HORAS, PISO_HORA),
        "ranking": ranking[:10],
    }


def carregar() -> dict:
    return _ler(ARQ_SAIDA, {})


def _escolha_ponderada(seed: str, opcoes: list[str], pesos: dict) -> str:
    """Escolha determinística pela seed, proporcional aos pesos (portável p/ JS)."""
    total = sum(pesos.get(str(o), 1) for o in opcoes)
    alvo = _fnv(seed) % total
    acumulado = 0
    for op in opcoes:
        acumulado += pesos.get(str(op), 1)
        if alvo < acumulado:
            return str(op)
    return str(opcoes[-1])


def escolher_estilo_ponderado(seed: str) -> str | None:
    pesos = carregar().get("pesos_estilo")
    if not pesos:
        return None
    # sal "estiloD": re-rolagem escolhida em 15/08 — o sal original deixava a
    # janela de agosto quase sem o estilo foto (azar do hash, não viés)
    return _escolha_ponderada(seed + "estiloD", ESTILOS, pesos)


def bucket_ponderado(seed: str) -> str | None:
    pesos = carregar().get("pesos_tamanho")
    if not pesos:
        return None
    return _escolha_ponderada(seed + "tam", TAMANHOS, pesos)


def hora_do_dia(dia: datetime.date) -> int:
    """A que horas (Brasília) o post daquele dia deve sair. Determinístico."""
    pesos = carregar().get("pesos_hora")
    if not pesos:
        return HORAS[0]
    return int(_escolha_ponderada(dia.isoformat() + "hora", [str(h) for h in HORAS], pesos))


def tamanho_do_texto(texto: str) -> str:
    return _bucket(len(texto))


def main() -> int:
    dados = aprender()
    ARQ_SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[inteligencia] {dados['amostras']} amostras")
    print(f"[inteligencia] estilos: {dados['pesos_estilo']}")
    print(f"[inteligencia] tamanhos: {dados['pesos_tamanho']}")
    print(f"[inteligencia] horas: {dados['pesos_hora']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
