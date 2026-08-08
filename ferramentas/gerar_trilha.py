"""Gera uma trilha instrumental ORIGINAL (sintetizada) para os vídeos.

Nada de sample nem de música do catálogo do Instagram — cada nota é uma soma de
senoides calculada aqui. Por isso não há risco de direitos autorais: a faixa é
100% gerada.

Pegada ANIMADA: andamento dobrado (acordes de 2s, ~120 BPM), progressão maior
(Dó–Fá–Sol–Dó repetida), baixo marcando o ritmo (groove) e arpejo rápido tipo
caixinha de música por cima. Sem drone grave triste.

    python3 ferramentas/gerar_trilha.py      # grava audio/trilha.wav

Se um dia o Gabriel quiser outra música, é só substituir audio/trilha.wav — o
resto do pipeline não muda.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "audio" / "trilha.wav"

SR = 22050
SEG = 2.0          # segundos por acorde (~120 BPM, andamento animado)
CF = 0.6           # crossfade entre acordes (segundos)
TOTAL = 16.0       # 8 acordes × 2 s — a progressão roda 2x; laço perfeito

NOTAS = {
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.00,
    "A4": 440.00, "B4": 493.88, "C5": 523.25, "D5": 587.33, "E5": 659.25,
}
# I–IV–V–I em Dó maior, tudo MAIOR, tocado duas vezes — arco que sobe e resolve alegre.
PROGRESSAO = [
    ["C4", "E4", "G4"],   # C  (I)
    ["F4", "A4", "C5"],   # F  (IV)
    ["G4", "B4", "D5"],   # G  (V)
    ["C4", "E4", "G4"],   # C  (I) — resolve
]
ACORDES = PROGRESSAO * 2

# Pad: fundamental + harmônicos suaves. Sem sub-oitava (era ela que pesava/entristecia).
PARCIAIS = [(1.0, 1.0), (2.0, 0.5), (3.0, 0.22), (4.0, 0.10)]

# Baixo marcando o ritmo (groove) e arpejo rápido (caixinha de música) por cima.
PASSO_BAIXO = 0.5   # uma nota de baixo por tempo (~120 BPM)
PASSO_ARP = 0.25    # arpejo em colcheias — corrido, animado
TAU_ARP = 0.16      # decaimento curto do pluck (segundos)
TAU_BAIXO = 0.24


def _voz(freq: float, t: float) -> float:
    val = 0.0
    for mult, amp in PARCIAIS:
        val += amp * math.sin(2 * math.pi * freq * mult * t)
        val += amp * 0.5 * math.sin(2 * math.pi * freq * mult * 1.004 * t)  # chorus leve
    return val


def _pluck(freq: float, t: float, tau: float = TAU_ARP) -> float:
    if t < 0:
        return 0.0
    ataque = 1 - math.exp(-t / 0.004)        # ataque quase instantâneo
    decai = math.exp(-t / tau)               # cauda curta, tipo caixinha
    tom = math.sin(2 * math.pi * freq * t) + 0.35 * math.sin(2 * math.pi * freq * 2 * t)
    return ataque * decai * tom


def _envelope(t: float, dur: float) -> float:
    """Fade-in/out em cosseno levantado; a sobreposição vira crossfade."""
    if t < CF:
        return 0.5 * (1 - math.cos(math.pi * t / CF))
    if t > dur - CF:
        return 0.5 * (1 - math.cos(math.pi * (dur - t) / CF))
    return 1.0


def gerar(nome: str = "trilha.wav", semitons: int = 0, desce: bool = False) -> Path:
    """Gera uma variação da trilha. `semitons` transpõe (chave diferente); `desce`
    inverte o sentido do arpejo. Mesma pegada animada, timbre reconhecível."""
    fator = 2.0 ** (semitons / 12.0)
    destino = RAIZ / "audio" / nome
    n_total = int(TOTAL * SR)
    buf = [0.0] * n_total
    dur_janela = SEG + CF
    n_janela = int(dur_janela * SR)

    for i, acorde in enumerate(ACORDES):
        freqs = [NOTAS[n] * fator for n in acorde]
        inicio = int((i * SEG - CF / 2) * SR)  # pode ser negativo → dá a volta (laço)

        # Pad sustentado, discreto — só o colchão de harmonia.
        for n in range(n_janela):
            t = n / SR
            env = _envelope(t, dur_janela)
            if env <= 0:
                continue
            amostra = sum(_voz(f, t) for f in freqs) / len(freqs)
            buf[(inicio + n) % n_total] += 0.4 * env * amostra

        base = int(i * SEG * SR)

        # Baixo marcando o tempo (root uma oitava abaixo) — dá o groove animado.
        for k in range(int(SEG / PASSO_BAIXO)):
            freq = freqs[0] * 0.5
            t0 = int((k * PASSO_BAIXO) * SR)
            dur = int(min(PASSO_BAIXO + TAU_BAIXO * 3, SEG) * SR)
            for n in range(dur):
                buf[(base + t0 + n) % n_total] += 0.55 * _pluck(freq, n / SR, TAU_BAIXO)

        # Arpejo rápido por cima: sobe/desce pelas notas do acorde, uma oitava acima.
        subida = freqs + freqs[::-1][1:-1]  # C E G E → padrão que sobe e desce
        if desce:
            subida = subida[::-1]
        for k in range(int(SEG / PASSO_ARP)):
            freq = subida[k % len(subida)] * 2.0
            t0 = int((k * PASSO_ARP) * SR)
            dur = int(min(PASSO_ARP + TAU_ARP * 3, SEG) * SR)
            for n in range(dur):
                buf[(base + t0 + n) % n_total] += 0.42 * _pluck(freq, n / SR)

    pico = max(abs(v) for v in buf) or 1.0
    ganho = 0.6 / pico  # headroom; é trilha de fundo

    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(
            b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v * ganho)) * 32767)) for v in buf)
        )
    return destino


# Três variações em rotação (o vídeo escolhe uma por dia). Mesma pegada, chaves
# diferentes + sentido do arpejo variado, para o feed não soar sempre igual.
VARIACOES = [
    ("trilha.wav", 0, False),    # Dó
    ("trilha2.wav", 2, True),    # Ré (mais brilhante), arpejo descendente
    ("trilha3.wav", -3, False),  # Lá (mais quente)
]


if __name__ == "__main__":
    for nome, semitons, desce in VARIACOES:
        caminho = gerar(nome, semitons, desce)
        print(f"[trilha] {caminho.name} ({caminho.stat().st_size // 1024} KB, {TOTAL:.0f}s)")
