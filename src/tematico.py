"""
Carrossel temático (quarta e sexta, desde 29/10/2026): "5 versículos para
quando…". É o formato que mais se guarda e se envia — exatamente os sinais que
estavam em quase zero (0,4 salvo e 0,6 envio por post em 81 posts). O carrossel
de domingo (src/semanal.py, a semana que vem) continua igual.

Capa com o tema → 5 versículos do acervo com aquele tema, todos no mesmo estilo
→ fecho pedindo salvar/enviar. Tema gira por semana/dia; os versículos evitam os
do último carrossel do mesmo tema. Registro em dados/tematicos.json.

    python3 -m src.tematico --fase preparar | publicar | ensaio
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from src import imagem, instagram, legenda, versiculos
from src.principal import url_publica

RAIZ = Path(__file__).resolve().parent.parent
DIR = RAIZ / "posts" / "tematico"
ARQ_LISTA = DIR / "itens.json"
ARQ_LEGENDA = DIR / "legenda.txt"
ARQ_REGISTRO = RAIZ / "dados" / "tematicos.json"

QUANTOS = 5
ESTILOS = ["classico", "livro", "foto"]

# (chave, título da capa, hashtags do acervo que entram, hashtags da legenda)
TEMAS = [
    ("ansiedade", "5 versículos para quando a ansiedade apertar",
     {"ansiedade", "paz", "descanso", "presenca"}, ["ansiedade", "paz", "saudemental"]),
    ("desistir", "5 versículos para quem pensou em desistir",
     {"forca", "coragem", "animo", "perseveranca", "recomeco"}, ["forca", "naodesista", "coragem"]),
    ("espera", "5 versículos para quem está esperando uma resposta",
     {"esperanca", "confianca", "proposito", "direcao"}, ["esperanca", "confianca", "propositodedeus"]),
    ("medo", "5 versículos para quando bater o medo",
     {"semmedo", "protecao", "seguranca", "refugio"}, ["semmedo", "protecao", "deusnocontrole"]),
    ("amor", "5 versículos sobre o quanto Deus ama você",
     {"amor", "amordedeus", "graca", "misericordia"}, ["amordedeus", "graca", "misericordia"]),
    ("dor", "5 versículos para quem está sofrendo",
     {"consolo", "cura", "coracao", "presenca"}, ["consolo", "cura", "fe"]),
    ("gratidao", "5 versículos para começar o dia agradecendo",
     {"gratidao", "louvor", "alegria", "adoracao"}, ["gratidao", "louvor", "alegria"]),
    ("sabedoria", "5 versículos para decidir com sabedoria",
     {"sabedoria", "mente", "proverbios", "direcao"}, ["sabedoria", "proverbios", "direcao"]),
]
HASHTAGS_BASE = ["versiculododia", "versiculosbiblicos", "palavradedeus", "biblia", "fecrista", "devocional"]


def _ler(caminho: Path, padrao):
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else padrao


def _fnv(texto: str) -> int:
    h = 2166136261
    for ch in texto:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


def montar(dia: datetime.date) -> dict | None:
    # 2 carrosséis por semana: o índice anda de 1 em 1 a cada publicação.
    semana = dia.isocalendar()[1]
    indice = semana * 2 + (1 if dia.weekday() >= 4 else 0)
    chave, titulo, tags, tags_legenda = TEMAS[indice % len(TEMAS)]

    reflexoes = json.loads((RAIZ / "dados" / "reflexoes.json").read_text(encoding="utf-8"))
    pool = versiculos.carregar_pool()
    ultimo = next((r for r in reversed(_ler(ARQ_REGISTRO, [])) if r["tema"] == chave), None)
    usados = set(ultimo["consultas"]) if ultimo else set()
    candidatos = [
        v for v in pool
        if set(reflexoes.get(v.consulta, {}).get("hashtags", [])) & tags and len(v.texto) <= 260
    ]
    # Prefere os que não saíram no último carrossel do tema.
    # Mais tags do tema em comum primeiro (o mais "no tema"); ordem estável pelo dia.
    afinidade = {v.consulta: len(set(reflexoes[v.consulta].get("hashtags", [])) & tags) for v in candidatos}
    candidatos.sort(key=lambda v: (v.consulta in usados, -afinidade[v.consulta],
                                   _fnv(v.consulta + dia.isoformat())))
    escolhidos = candidatos[:QUANTOS]
    if len(escolhidos) < 3:
        return None
    seed = f"tema-{dia.isoformat()}"
    return {
        "data": dia.isoformat(), "tema": chave, "titulo": titulo,
        "estilo": ESTILOS[_fnv(seed) % len(ESTILOS)], "seed": seed,
        "tags_legenda": tags_legenda,
        "itens": [{"consulta": v.consulta, "referencia": v.referencia, "texto": v.texto} for v in escolhidos],
    }


def _legenda(plano: dict) -> str:
    refs = "\n".join(f"{i + 1}. {it['referencia']}" for i, it in enumerate(plano["itens"]))
    tags = list(dict.fromkeys(plano["tags_legenda"] + HASHTAGS_BASE))[:legenda.MAX_HASHTAGS]
    return (
        f"{plano['titulo']} 🙏\n\n"
        f"Arraste para o lado e leia com calma:\n{refs}\n\n"
        "Qual deles falou mais com você? Salve para reler e envie para alguém que precisa. 💛\n\n"
        + " ".join("#" + t for t in tags)
    )


def preparar(dia: datetime.date, ensaio: bool) -> int:
    plano = montar(dia)
    if plano is None:
        print("::error::Poucos versículos no acervo para o tema de hoje.", file=sys.stderr)
        return 1
    DIR.mkdir(parents=True, exist_ok=True)
    for antigo in DIR.glob("*.jpg"):
        antigo.unlink()
    arquivos = ["00-capa.jpg"]
    imagem.gerar_capa_tema(plano["titulo"], DIR / "00-capa.jpg", plano["seed"])
    for i, it in enumerate(plano["itens"], 1):
        nome = f"{i:02d}.jpg"
        imagem.gerar_quadrado_estilo(it["texto"], it["referencia"], DIR / nome,
                                     seed=f"{plano['seed']}-{i}", estilo=plano["estilo"])
        arquivos.append(nome)
    imagem.gerar_fecho_tema(DIR / "99-fecho.jpg", plano["seed"])
    arquivos.append("99-fecho.jpg")
    plano["arquivos"] = arquivos
    ARQ_LISTA.write_text(json.dumps(plano, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ARQ_LEGENDA.write_text(_legenda(plano) + "\n", encoding="utf-8")
    print(f"[tematico] {plano['titulo']} ({plano['estilo']}): {len(arquivos)} imagens")
    print(f"[legenda]\n{_legenda(plano)}\n")
    if ensaio:
        print("[ensaio] carrossel gerado; nada foi publicado")
    return 0


def publicar(dia: datetime.date) -> int:
    if not ARQ_LISTA.exists():
        print("::error::Carrossel não preparado — rode a fase preparar.", file=sys.stderr)
        return 1
    plano = json.loads(ARQ_LISTA.read_text(encoding="utf-8"))
    registro = _ler(ARQ_REGISTRO, [])
    if any(r["data"] == plano["data"] for r in registro):
        print("[tematico] já publicado hoje; nada a fazer")
        return 0
    urls = [url_publica(f"posts/tematico/{nome}") for nome in plano["arquivos"]]
    try:
        id_post = instagram.publicar_carrossel(urls, ARQ_LEGENDA.read_text(encoding="utf-8").strip())
    except instagram.ErroInstagram as erro:
        print(f"::error::Falha ao publicar o carrossel temático: {erro}", file=sys.stderr)
        return 1
    print(f"[instagram] carrossel temático publicado: {id_post}")
    registro.append({"data": plano["data"], "tema": plano["tema"], "id_post": id_post,
                     "consultas": [it["consulta"] for it in plano["itens"]]})
    ARQ_REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    opcoes = argparse.ArgumentParser()
    opcoes.add_argument("--fase", choices=("preparar", "publicar", "ensaio"), required=True)
    argumentos = opcoes.parse_args()
    hoje = datetime.date.today()
    if argumentos.fase == "publicar":
        return publicar(hoje)
    return preparar(hoje, ensaio=argumentos.fase == "ensaio")


if __name__ == "__main__":
    raise SystemExit(main())
