"""Escolha do versículo do dia, sem repetir enquanto houver inéditos."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_POOL = RAIZ / "dados" / "versiculos.json"
ARQUIVO_HISTORICO = RAIZ / "dados" / "historico.json"
ARQUIVO_AGENDA = RAIZ / "dados" / "agenda.json"
# Versículos a NÃO sortear por enquanto (lista de consultas). Útil para "pular"
# um versículo sem inventar um post falso no histórico. O sorteio trata como já
# usado; quando o pool inteiro se esgota, eles voltam à rotação normalmente.
ARQUIVO_RESERVADOS = RAIZ / "dados" / "reservados.json"
# Datas com versículo fixo (Natal, Páscoa, Ano Novo). Chave "MM-DD" vale todo
# ano; "YYYY-MM-DD" vale só naquele dia (útil para a Páscoa, que muda de data).
ARQUIVO_DATAS = RAIZ / "dados" / "datas_especiais.json"
ARQUIVO_REFLEXOES = RAIZ / "dados" / "reflexoes.json"

# Tema por dia da semana (índice do Python: segunda=0 … domingo=6). Cada tema é
# um conjunto de hashtags; um versículo "combina" com o dia se tiver alguma delas.
# É um VIÉS, não um filtro rígido: se não houver versículo temático inédito, cai
# no sorteio normal (fallback), então nunca trava.
TEMAS_DIA = {
    0: {"forca", "coragem", "recomeco", "novavida", "proposito", "animo", "perseveranca", "semmedo"},
    1: {"esperanca", "confianca", "refugio", "bencao"},
    2: {"sabedoria", "mente", "proverbios"},
    3: {"amor", "amordedeus", "relacionamentos", "amizade", "perdao"},
    4: {"paz", "descanso", "ansiedade", "consolo", "presenca", "saudemental"},
    5: {"protecao", "seguranca", "provisao", "cura", "direcao", "oracao", "coracao"},
    6: {"gratidao", "louvor", "adoracao", "alegria", "graca", "misericordia", "evangelho", "salvacao"},
}
TEMAS_NOME = {
    0: "Força e recomeço", 1: "Fé e esperança", 2: "Sabedoria", 3: "Amor",
    4: "Paz e descanso", 5: "Proteção e cuidado", 6: "Gratidão e louvor",
}


@dataclass(frozen=True)
class Versiculo:
    referencia: str
    texto: str
    consulta: str


def carregar_pool() -> list[Versiculo]:
    dados = json.loads(ARQUIVO_POOL.read_text(encoding="utf-8"))
    if not dados:
        raise RuntimeError("dados/versiculos.json está vazio — rode ferramentas/montar_pool.py")
    return [Versiculo(**item) for item in dados]


def carregar_historico() -> list[dict]:
    if not ARQUIVO_HISTORICO.exists():
        return []
    return json.loads(ARQUIVO_HISTORICO.read_text(encoding="utf-8"))


def carregar_reservados() -> set[str]:
    if not ARQUIVO_RESERVADOS.exists():
        return set()
    return set(json.loads(ARQUIVO_RESERVADOS.read_text(encoding="utf-8")))


def carregar_datas() -> dict:
    if not ARQUIVO_DATAS.exists():
        return {}
    return json.loads(ARQUIVO_DATAS.read_text(encoding="utf-8"))


def carregar_temas() -> dict[str, set[str]]:
    """consulta -> conjunto de hashtags (lido das reflexões), para casar com o tema do dia."""
    if not ARQUIVO_REFLEXOES.exists():
        return {}
    refl = json.loads(ARQUIVO_REFLEXOES.read_text(encoding="utf-8"))
    return {consulta: set(dados.get("hashtags", [])) for consulta, dados in refl.items()}


def _consulta_de(entrada) -> str:
    """Uma entrada de data especial é a consulta (str) ou {consulta, exclusivo}."""
    return entrada["consulta"] if isinstance(entrada, dict) else entrada


def _versiculo_da_data(dia: date, pool: list[Versiculo]) -> Versiculo | None:
    """Se o dia for uma data especial, devolve o versículo fixo dela (senão None)."""
    datas = carregar_datas()
    entrada = datas.get(dia.isoformat()) or datas.get(dia.strftime("%m-%d"))
    if not entrada:
        return None
    consulta = _consulta_de(entrada)
    return next((v for v in pool if v.consulta == consulta), None)


def _consultas_exclusivas() -> set[str]:
    """Versículos que só podem sair na data especial deles (Natal, Páscoa)."""
    return {
        _consulta_de(e)
        for e in carregar_datas().values()
        if isinstance(e, dict) and e.get("exclusivo")
    }


def registrar(
    versiculo: Versiculo, dia: date, id_post: str | None, extras: dict | None = None
) -> None:
    """Grava o post no histórico. `extras` guarda as características do post
    (estilo, hora, trilha) — é o que permite à inteligência aprender o que rende."""
    historico = carregar_historico()
    registro = {
        "data": dia.isoformat(),
        "consulta": versiculo.consulta,
        "referencia": versiculo.referencia,
        "id_post": id_post,
    }
    if extras:
        registro.update(extras)
    historico.append(registro)
    ARQUIVO_HISTORICO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_HISTORICO.write_text(
        json.dumps(historico, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def escolher(
    dia: date | None = None,
    pool: list[Versiculo] | None = None,
    historico: list[dict] | None = None,
    reservados: set[str] | None = None,
    temas: dict[str, set[str]] | None = None,
) -> Versiculo:
    """
    Sorteia entre os que ainda não foram publicados. Quando o pool se esgota,
    recomeça pelos mais antigos — assim nunca trava por falta de versículo novo.

    O sorteio é semeado pela data: rodar duas vezes no mesmo dia (um retry do
    workflow, por exemplo) escolhe o mesmo versículo em vez de queimar outro.

    Cada dia da semana tem um tema (ver TEMAS_DIA); a escolha prioriza versículos
    do tema do dia, mas cai no sorteio geral se não houver inédito temático.

    `pool`, `historico` e `temas` podem ser passados em memória para simular dias
    futuros sem reler o disco a cada passo (usado por `simular_agenda`).
    """
    dia = dia or date.today()
    if pool is None:
        pool = carregar_pool()
    if historico is None:
        historico = carregar_historico()
    if reservados is None:
        reservados = carregar_reservados()
    if temas is None:
        temas = carregar_temas()

    # Data especial manda: Natal, Páscoa, Ano Novo têm versículo fixo.
    especial = _versiculo_da_data(dia, pool)
    if especial is not None:
        return especial

    # Versículos exclusivos (Natal, Páscoa) saem SÓ na data deles — fora dela,
    # ficam fora do sorteio normal para não aparecerem na época errada.
    ja_usados = {item["consulta"] for item in historico} | reservados | _consultas_exclusivas()
    ineditos = [v for v in pool if v.consulta not in ja_usados]

    if ineditos:
        # Viés pelo tema do dia; fallback para todos os inéditos se o tema secar.
        tags_dia = TEMAS_DIA.get(dia.weekday(), set())
        tematicos = [v for v in ineditos if temas.get(v.consulta, set()) & tags_dia]
        candidatos = tematicos or ineditos
        # Segundo viés: a inteligência aprende qual TAMANHO de versículo rende
        # mais (curto/médio/longo) e puxa a escolha para lá — com fallback se
        # não houver candidato daquele tamanho.
        from src import inteligencia
        bucket = inteligencia.bucket_ponderado(dia.isoformat())
        if bucket:
            do_tamanho = [v for v in candidatos if inteligencia.tamanho_do_texto(v.texto) == bucket]
            candidatos = do_tamanho or candidatos
    else:
        # Pool esgotado: reabre pelos publicados há mais tempo.
        ultima_vez = {}
        for item in historico:
            ultima_vez[item["consulta"]] = item["data"]
        candidatos = sorted(pool, key=lambda v: ultima_vez.get(v.consulta, ""))
        candidatos = candidatos[: max(5, len(pool) // 4)]

    sorteio = random.Random(dia.isoformat())
    return sorteio.choice(candidatos)


def simular_agenda(dias: int = 14, hoje: date | None = None) -> list[dict]:
    """
    Prevê quais versículos sairão nos próximos dias.

    A escolha é determinística dado (data, histórico), então dá para simular o
    futuro: escolhe para um dia, finge que aquele post aconteceu e segue para o
    próximo. Bate com a realidade enquanto o pool não mudar. A página de controle
    lê o resultado — em vez de tentar reproduzir o sorteador do Python em JS, o
    que não é portável.
    """
    hoje = hoje or date.today()
    pool = carregar_pool()
    historico = [dict(h) for h in carregar_historico()]  # cópia mutável
    reservados = carregar_reservados()
    temas = carregar_temas()
    ja = {h["data"] for h in historico}

    # A agenda começa no primeiro dia que ainda não tem post.
    d = hoje
    while d.isoformat() in ja:
        d = d + timedelta(days=1)

    agenda = []
    for _ in range(dias):
        v = escolher(d, pool=pool, historico=historico, reservados=reservados, temas=temas)
        from src import inteligencia
        agenda.append({
            "data": d.isoformat(),
            "referencia": v.referencia,
            "consulta": v.consulta,
            "tema": TEMAS_NOME.get(d.weekday(), ""),
            "hora": inteligencia.hora_do_dia(d),
        })
        historico.append(
            {"data": d.isoformat(), "consulta": v.consulta, "referencia": v.referencia, "id_post": None}
        )
        d = d + timedelta(days=1)
    return agenda


def escrever_agenda(dias: int = 14) -> None:
    """Grava a agenda prevista em dados/agenda.json (a página de controle lê daqui)."""
    ARQUIVO_AGENDA.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_AGENDA.write_text(
        json.dumps(simular_agenda(dias), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
