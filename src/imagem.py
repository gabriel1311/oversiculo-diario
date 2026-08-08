"""Renderiza o post 1080x1080 a partir do versículo.

O visual varia por dia — paleta, ornamento e moldura — para o feed não ficar
engessado, mas a estrutura é sempre a mesma (versículo centralizado, referência,
assinatura, moldura dourada). A variação é semeada pela data: o mesmo dia sempre
sai igual (retry seguro), dias diferentes saem diferentes.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
FONTES = RAIZ / "fontes"

LADO = 1080
MARGEM = 96

# Paletas: fundo escuro + tinta clara + acento metálico. Todas são claro-sobre-
# escuro com contraste alto, então o texto fica sempre legível. O acento é uma
# variação de dourado/bronze que combina com cada fundo.
PALETAS = [
    {  # marinho (o original)
        "topo": (11, 29, 58), "base": (24, 52, 94), "vinheta": (4, 12, 26),
        "ouro": (206, 170, 106), "ouro_fraco": (150, 122, 76), "texto": (243, 240, 233),
    },
    {  # floresta
        "topo": (10, 40, 30), "base": (18, 60, 45), "vinheta": (4, 18, 12),
        "ouro": (200, 172, 108), "ouro_fraco": (142, 120, 78), "texto": (240, 240, 230),
    },
    {  # vinho
        "topo": (46, 16, 26), "base": (74, 28, 42), "vinheta": (22, 8, 14),
        "ouro": (208, 172, 112), "ouro_fraco": (152, 122, 82), "texto": (244, 236, 232),
    },
    {  # grafite (acento areia)
        "topo": (26, 28, 33), "base": (44, 47, 55), "vinheta": (10, 11, 14),
        "ouro": (212, 188, 152), "ouro_fraco": (150, 132, 106), "texto": (240, 238, 232),
    },
    {  # ameixa
        "topo": (36, 22, 52), "base": (58, 38, 80), "vinheta": (16, 10, 26),
        "ouro": (202, 172, 122), "ouro_fraco": (146, 122, 88), "texto": (242, 236, 240),
    },
    {  # petróleo
        "topo": (8, 38, 44), "base": (14, 60, 68), "vinheta": (4, 18, 20),
        "ouro": (200, 178, 124), "ouro_fraco": (140, 124, 88), "texto": (236, 240, 238),
    },
    {  # café
        "topo": (34, 24, 18), "base": (58, 42, 30), "vinheta": (16, 10, 6),
        "ouro": (214, 184, 130), "ouro_fraco": (154, 130, 92), "texto": (242, 236, 226),
    },
]

MOLDURAS = ["dupla", "cantos"]
ORNAMENTOS = ["losango", "cruz", "pontos"]

HANDLE = "@oversiculo.diario"


def _fonte(arquivo: str, tamanho: int, peso: str = "Regular") -> ImageFont.FreeTypeFont:
    """
    Carrega uma fonte variável já fixada num peso.

    As duas fontes do projeto são variáveis (um arquivo cobre vários pesos), mas
    não oferecem os mesmos: EB Garamond vai de Regular a ExtraBold, Cinzel tem só
    Regular/Bold/Black. Pedir um peso inexistente levanta ValueError, então
    caímos no mais próximo disponível em vez de quebrar o render.
    """
    fonte = ImageFont.truetype(str(FONTES / arquivo), tamanho)
    try:
        disponiveis = [
            n.decode() if isinstance(n, bytes) else n for n in fonte.get_variation_names()
        ]
    except OSError:
        return fonte  # fonte estática — o peso já é o do arquivo

    if peso not in disponiveis:
        escala = ["Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"]
        alvo = escala.index(peso) if peso in escala else 0
        peso = min(
            disponiveis,
            key=lambda n: abs((escala.index(n) if n in escala else 0) - alvo),
        )
    fonte.set_variation_by_name(peso)
    return fonte


def _fundo(pal: dict) -> Image.Image:
    """Gradiente vertical suave com vinheta, montado pequeno e ampliado."""
    altura = 256
    gradiente = Image.new("RGB", (1, altura))
    pixels = gradiente.load()
    for y in range(altura):
        proporcao = y / (altura - 1)
        pixels[0, y] = tuple(
            round(pal["topo"][c] + (pal["base"][c] - pal["topo"][c]) * proporcao)
            for c in range(3)
        )
    base = gradiente.resize((LADO, LADO), Image.Resampling.BICUBIC)

    # Vinheta: escurece os cantos para o texto ganhar peso no centro.
    vinheta = Image.radial_gradient("L").resize((LADO, LADO), Image.Resampling.BICUBIC)
    escuro = Image.new("RGB", (LADO, LADO), pal["vinheta"])
    return Image.composite(escuro, base, vinheta.point(lambda v: int(v * 0.55)))


def _moldura(desenho: ImageDraw.ImageDraw, pal: dict, estilo: str) -> None:
    if estilo == "cantos":
        # Só cantos: quatro cotovelos dourados, sem retângulo fechado.
        m, braco = 54, 70
        for cx, cy, sx, sy in [
            (m, m, 1, 1),
            (LADO - m, m, -1, 1),
            (m, LADO - m, 1, -1),
            (LADO - m, LADO - m, -1, -1),
        ]:
            desenho.line([cx, cy, cx + sx * braco, cy], fill=pal["ouro"], width=2)
            desenho.line([cx, cy, cx, cy + sy * braco], fill=pal["ouro"], width=2)
        return

    # dupla (padrão): duas linhas concêntricas.
    externa, interna = 44, 60
    desenho.rectangle(
        [externa, externa, LADO - externa - 1, LADO - externa - 1],
        outline=pal["ouro_fraco"], width=2,
    )
    desenho.rectangle(
        [interna, interna, LADO - interna - 1, LADO - interna - 1],
        outline=pal["ouro"], width=1,
    )


def _quebrar(
    texto: str, fonte: ImageFont.FreeTypeFont, largura_maxima: int, desenho: ImageDraw.ImageDraw
) -> list[str]:
    linhas: list[str] = []
    atual = ""
    for palavra in texto.split():
        tentativa = f"{atual} {palavra}".strip()
        if desenho.textlength(tentativa, font=fonte) <= largura_maxima:
            atual = tentativa
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _ajustar(
    texto: str, desenho: ImageDraw.ImageDraw, largura: int, altura: int
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    """
    Encolhe a fonte até o versículo caber na área reservada.

    Versículos longos existem no pool (1 Coríntios 13:4-7 tem 315 caracteres),
    então isto não é um caso hipotético — sem o ajuste o texto vaza da moldura.
    """
    for tamanho in range(64, 27, -2):
        fonte = _fonte("EBGaramond.ttf", tamanho, "Regular")
        linhas = _quebrar(texto, fonte, largura, desenho)
        espacamento = round(tamanho * 1.42)
        if len(linhas) * espacamento <= altura:
            return fonte, linhas, espacamento
    fonte = _fonte("EBGaramond.ttf", 28, "Regular")
    return fonte, _quebrar(texto, fonte, largura, desenho), 40


def _ornamento(desenho: ImageDraw.ImageDraw, centro_y: int, pal: dict, estilo: str) -> None:
    meio = LADO // 2
    largura = 90
    # Os dois traços laterais aparecem em todos os estilos.
    desenho.line([meio - largura, centro_y, meio - 16, centro_y], fill=pal["ouro_fraco"], width=1)
    desenho.line([meio + 16, centro_y, meio + largura, centro_y], fill=pal["ouro_fraco"], width=1)

    if estilo == "cruz":
        desenho.line([meio, centro_y - 8, meio, centro_y + 8], fill=pal["ouro"], width=2)
        desenho.line([meio - 6, centro_y - 2, meio + 6, centro_y - 2], fill=pal["ouro"], width=2)
    elif estilo == "pontos":
        for dx in (-8, 0, 8):
            desenho.ellipse(
                [meio + dx - 2, centro_y - 2, meio + dx + 2, centro_y + 2], fill=pal["ouro"]
            )
    else:  # losango
        desenho.polygon(
            [(meio, centro_y - 6), (meio + 6, centro_y), (meio, centro_y + 6), (meio - 6, centro_y)],
            outline=pal["ouro"],
        )


def gerar(texto: str, referencia: str, destino: Path, seed: str | None = None) -> Path:
    # A data semeia paleta/moldura/ornamento: mesmo dia = mesmo visual (retry
    # seguro), dias diferentes = visuais diferentes.
    sorteio = random.Random(seed or "")
    pal = sorteio.choice(PALETAS)
    estilo_moldura = sorteio.choice(MOLDURAS)
    estilo_ornamento = sorteio.choice(ORNAMENTOS)

    imagem = _fundo(pal)
    desenho = ImageDraw.Draw(imagem)
    _moldura(desenho, pal, estilo_moldura)

    largura_util = LADO - 2 * MARGEM - 60
    altura_util = 470

    # Aspas decorativas
    aspas = _fonte("EBGaramond.ttf", 190, "Medium")
    desenho.text((MARGEM + 18, 150), "“", font=aspas, fill=pal["ouro_fraco"])

    fonte_texto, linhas, espacamento = _ajustar(texto, desenho, largura_util, altura_util)

    bloco = len(linhas) * espacamento
    y = 300 + (altura_util - bloco) // 2
    for linha in linhas:
        desenho.text((LADO // 2, y), linha, font=fonte_texto, fill=pal["texto"], anchor="ma")
        y += espacamento

    _ornamento(desenho, y + 44, pal, estilo_ornamento)

    fonte_referencia = _fonte("Cinzel.ttf", 40, "SemiBold")
    desenho.text(
        (LADO // 2, y + 88), referencia.upper(), font=fonte_referencia, fill=pal["ouro"], anchor="ma"
    )

    fonte_handle = _fonte("Cinzel.ttf", 21, "Regular")
    desenho.text(
        (LADO // 2, LADO - 118),
        " ".join(HANDLE.upper()),  # espaçado, como marca d'água discreta
        font=fonte_handle,
        fill=pal["ouro_fraco"],
        anchor="ma",
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    # JPEG e não PNG: a Graph API do Instagram aceita **apenas** JPEG para
    # publicação de imagem. Subsampling desligado (4:4:4) porque o padrão 4:2:0
    # borra o dourado fino da moldura e da referência sobre o fundo azul.
    imagem.save(destino, "JPEG", quality=93, subsampling=0, optimize=True, progressive=False)
    return destino
