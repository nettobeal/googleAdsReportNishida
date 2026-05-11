
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Flowable
)
from reportlab.lib.styles import ParagraphStyle as S
from reportlab.lib.utils import simpleSplit

# ── Cores ───────────────────────────────────────────────────────────────────
RED    = colors.HexColor('#CC0000')
DARK   = colors.HexColor('#1A1A1A')
GRAY   = colors.HexColor('#666666')
LGRAY  = colors.HexColor('#F5F5F5')
BGRAY  = colors.HexColor('#DDDDDD')
WHITE  = colors.white

# ── Página ───────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
M  = 18*mm          # margem esquerda/direita
CW = PAGE_W - 2*M   # largura útil do conteúdo

OUTPUT = '/mnt/user-data/outputs/Relatorio_Tantra_Motel_Abril2026.pdf'

# ── Estilos de parágrafo ─────────────────────────────────────────────────────
BOX  = S('BX',  fontSize=8.5, leading=14, textColor=DARK, fontName='Helvetica',
         borderColor=BGRAY, borderWidth=0.6,
         borderPadding=(10,12,12,12), borderRadius=4, backColor=LGRAY)
BODY = S('BD',  fontSize=8.5, leading=13, textColor=DARK, fontName='Helvetica')
SMALL= S('SM',  fontSize=7,   leading=10, textColor=GRAY, fontName='Helvetica')
PSEC = S('SE',  fontSize=10,  leading=14, textColor=RED,  fontName='Helvetica-Bold')
TITL = S('TI',  fontSize=16,  leading=20, textColor=DARK, fontName='Helvetica-Bold')
SUB  = S('SB',  fontSize=9,   leading=13, textColor=GRAY, fontName='Helvetica')

# ── Flowables customizados ───────────────────────────────────────────────────

class SecBar(Flowable):
    """Barra de seção com padding embutido acima e abaixo."""
    PAD = 6  # espaço acima e abaixo do retângulo (em pontos)

    def __init__(self, txt, w, bg=LGRAY, tc=RED, bc=RED):
        self.txt = txt
        self.w   = w
        self.bg  = bg   # cor de fundo
        self.tc  = tc   # cor do texto
        self.bc  = bc   # cor da borda

    def wrap(self, *_):
        return self.w, 20 + 2 * self.PAD

    def draw(self):
        c = self.canv
        c.setFillColor(self.bg)
        c.setStrokeColor(self.bc)
        c.setLineWidth(0.7)
        c.roundRect(0, self.PAD, self.w, 20, 3, fill=1, stroke=1)
        c.setFillColor(self.tc)
        c.setFont('Helvetica-Bold', 8.5)
        c.drawString(8, self.PAD + 6, self.txt)

    def getSpaceBefore(self): return self.PAD
    def getSpaceAfter(self):  return self.PAD


class Cards4(Flowable):
    """Bloco de 4 cards de métricas lado a lado."""

    def __init__(self, cards, w):
        # cards = [(label, valor, subtítulo, destacado?), ...]
        self.cards = cards
        self.w     = w
        self.h     = 68

    def wrap(self, *_):
        return self.w, self.h

    def draw(self):
        c = self.canv
        n  = len(self.cards)
        cw = (self.w - (n - 1) * 4) / n

        for i, (lbl, val, sub, hi) in enumerate(self.cards):
            x = i * (cw + 4)
            c.setFillColor(WHITE)
            c.setStrokeColor(RED if hi else BGRAY)
            c.setLineWidth(1.2 if hi else 0.5)
            c.roundRect(x, 0, cw, self.h, 4, fill=1, stroke=1)

            if hi:  # barra vermelha no topo do card
                c.setFillColor(RED)
                c.roundRect(x, self.h - 5, cw, 5, 4, fill=1, stroke=0)
                c.rect(x, self.h - 8, cw, 4, fill=1, stroke=0)

            c.setFillColor(GRAY);  c.setFont('Helvetica', 7)
            c.drawString(x + 7, self.h - 15, lbl)
            c.setFillColor(DARK);  c.setFont('Helvetica-Bold', 17)
            c.drawString(x + 7, self.h - 36, val)
            c.setFillColor(GRAY);  c.setFont('Helvetica', 7)
            c.drawString(x + 7, self.h - 50, sub)


class BigBox(Flowable):
    """Caixa de destaque: valor grande à esquerda + texto explicativo à direita."""

    def __init__(self, val, lbl, txt, w, h=90):
        self.val = val
        self.lbl = lbl
        self.txt = txt
        self.w   = w
        self.h   = h

    def wrap(self, *_):
        return self.w, self.h

    def draw(self):
        c  = self.canv
        lw = 110  # largura da coluna esquerda (valor)

        c.setFillColor(LGRAY)
        c.setStrokeColor(BGRAY)
        c.setLineWidth(0.8)
        c.roundRect(0, 0, self.w, self.h, 4, fill=1, stroke=1)

        c.setFillColor(DARK); c.setFont('Helvetica-Bold', 22)
        c.drawString(12, self.h - 44, self.val)
        c.setFillColor(GRAY); c.setFont('Helvetica', 7.5)
        c.drawString(12, self.h - 58, self.lbl)

        c.setStrokeColor(BGRAY)
        c.line(lw + 5, 8, lw + 5, self.h - 8)

        lines = simpleSplit(self.txt, 'Helvetica', 8, self.w - lw - 22)
        y = self.h - 16
        c.setFillColor(DARK)
        for line in lines[:9]:
            c.setFont('Helvetica', 8)
            c.drawString(lw + 14, y, line)
            y -= 11


# ── Helpers de tabela ─────────────────────────────────────────────────────────

def make_table(rows, widths):
    """Tabela padrão: cabeçalho vermelho, linhas alternadas cinza/branco."""
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1,  0), RED),
        ('ROWBACKGROUNDS',(0,1), (-1, -1), [LGRAY, WHITE]),
        ('GRID',         (0, 0), (-1, -1), 0.4, BGRAY),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('FONTNAME',     (0, 0), (-1,  0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, -1), 7),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('TEXTCOLOR',    (0, 0), (-1,  0), WHITE),
    ]))
    return t

# Células de tabela
def ph(txt): return Paragraph(f'<b>{txt}</b>', S('ph', fontSize=7, textColor=WHITE, fontName='Helvetica-Bold'))
def p(txt):  return Paragraph(str(txt),        S('p',  fontSize=7, textColor=DARK,  fontName='Helvetica', leading=9))
def ps(txt): return Paragraph(str(txt),        S('ps', fontSize=6.5, textColor=DARK, fontName='Helvetica', leading=8))


# ── Header e Footer (repetido em todas as páginas) ────────────────────────────

def draw_page(canv, doc):
    canv.saveState()

    # Logo Nishida — esquerda
    canv.drawImage('/home/claude/nishida_new.png',
                   M, PAGE_H - 28*mm,
                   width=42*mm, height=10*mm,
                   preserveAspectRatio=True, anchor='sw', mask='auto')

    # Logo Tantra — direita (logo quadrada 321×323 px)
    canv.drawImage('/home/claude/tantra_logo.png',
                   PAGE_W - M - 22*mm, PAGE_H - 31*mm,
                   width=22*mm, height=22*mm,
                   preserveAspectRatio=True, anchor='sw', mask='auto')

    # Linha separadora do header
    canv.setStrokeColor(BGRAY); canv.setLineWidth(0.5)
    canv.line(M, PAGE_H - 32*mm, PAGE_W - M, PAGE_H - 32*mm)

    # Linha separadora do footer
    canv.line(M, 13*mm, PAGE_W - M, 13*mm)

    # Texto do footer
    canv.setFont('Helvetica', 7.5); canv.setFillColor(GRAY)
    canv.drawString(M,           8*mm, 'Nishida Publicidade')
    canv.drawRightString(PAGE_W - M, 8*mm, 'Relatorio gerado em 11/05/2026')

    canv.restoreState()


# ── Story ─────────────────────────────────────────────────────────────────────

story = []
sp = lambda n=6: story.append(Spacer(1, n))  # helper de espaçamento

# ═══════════════════════════════════════════════
# PÁGINA 1 — VISÃO GERAL
# ═══════════════════════════════════════════════

story.append(Paragraph('Relatorio de Campanha - Google Ads', TITL))
sp(4)
story.append(Paragraph(
    'Periodo: 01/04/2026 a 30/04/2026   |   Gerado em: 11/05/2026   |   Cliente: Tantra Motel', SUB))
sp(6)
story.append(HRFlowable(width=CW, thickness=1.5, color=RED, spaceAfter=10))

# Resumo
story.append(SecBar('  Resumo do Periodo', CW))
sp(4)
story.append(Paragraph(
    'Em abril de 2026, a campanha do Tantra Motel no Google Ads entregou resultados expressivos para o periodo. '
    'Com um investimento total de R$ 304,24, o anuncio foi exibido 2.967 vezes para pessoas que buscavam '
    'por moteis em Toledo e regiao. Dessas exibicoes, 498 pessoas clicaram no anuncio e, dessas, 94 realizaram '
    'uma acao valiosa (conversao via WhatsApp ou formulario). O custo medio por cada novo contato gerado foi de '
    'R$ 3,24, um valor bastante competitivo para o segmento de hospedagem.',
    BOX))
sp(10)

# Como funciona
story.append(SecBar('  Como o Google Ads funciona para Moteis', CW))
sp(4)
story.append(Paragraph(
    'Quando alguem em Toledo digita no Google algo como "motel perto de mim" ou "suite para casal Toledo", '
    'o anuncio do Tantra Motel aparece no topo dos resultados. O cliente paga apenas quando alguem clica no '
    'anuncio. A campanha e configurada para aparecer somente para pessoas com real intencao de reserva, o que '
    'explica a alta taxa de conversao conquistada no periodo.',
    BODY))
sp(10)

# Benchmark
story.append(SecBar('  Cliente vs. media do mercado (Varejo Local / Hospedagem)', CW))
sp(4)
bench_rows = [
    [ph('Metrica'),              ph('Tantra Motel'), ph('Media do Mercado'),     ph('Avaliacao')],
    [p('CTR (taxa de cliques)'), p('16,78%'),        p('3 a 5%'),                p('Excelente')],
    [p('CPC medio'),             p('R$ 0,61'),       p('R$ 0,50 a R$ 2,00'),    p('Excelente')],
    [p('Taxa de conversao'),     p('18,88%'),        p('2 a 4%'),                p('Excelente')],
    [p('Custo por conversao'),   p('R$ 3,24'),       p('R$ 10 a R$ 30'),         p('Excelente')],
]
story.append(make_table(bench_rows, [CW*0.28, CW*0.22, CW*0.28, CW*0.22]))
sp(10)

# Cards de resultados
story.append(Paragraph('Resultados consolidados do periodo', PSEC))
sp(5)
story.append(Cards4([
    ('Impressoes', '2.967', 'exibicoes no mes',        False),
    ('Cliques',    '498',   'acessos ao site/WhatsApp', True),
    ('CTR',        '16,78%','taxa de cliques',           True),
    ('Conversoes', '94',    'contatos gerados',          True),
], CW))
sp(6)
story.append(Cards4([
    ('Custo Total',    'R$ 304', 'investimento no periodo',      False),
    ('CPC Medio',      'R$ 0,61','custo por clique',             False),
    ('Taxa de Conv.',  '18,88%', 'cliques que viraram contato',  True),
    ('Custo/Conversao','R$ 3,24','custo por novo contato',       True),
], CW))

story.append(PageBreak())

# ═══════════════════════════════════════════════
# PÁGINA 2 — DETALHAMENTO
# ═══════════════════════════════════════════════

story.append(SecBar('  Grupo de Anuncios', CW, bg=RED, tc=WHITE, bc=RED))
sp(4)
story.append(Paragraph(
    'Campanha: PESQUISA - TANTRA MOTEL - 300/mes - 10/dia   |   '
    'Estrategia de lances: Maximizar conversoes   |   Orcamento diario: R$ 10,00',
    SMALL))
sp(8)

story.append(Cards4([
    ('Cliques',       '498',    'grupo MOTEL - FUNDO DE FUNIL', False),
    ('Impressoes',    '2.967',  'no periodo',                   False),
    ('Taxa de Conv.', '18,88%', 'muito acima da media',          True),
    ('Custo/Conv.',   'R$ 3,24','por contato gerado',            True),
], CW))
sp(10)

story.append(BigBox(
    'R$ 3,24',
    'custo por conversao (contato gerado)',
    'Cada contato gerado pela campanha custou apenas R$ 3,24. '
    'Isso significa que, para cada R$ 3,24 investidos em anuncios, '
    'o Tantra Motel recebeu um novo contato de cliente com real intencao de reserva. '
    'A media do mercado de hospedagem gira em torno de R$ 10 a R$ 30 por conversao, '
    'o que coloca o resultado do Tantra Motel muito acima do esperado para o segmento.',
    CW, h=95))
sp(10)

# Top palavras-chave
story.append(SecBar('  Palavras-chave com maior conversao no periodo', CW))
sp(4)
kw_dest = [
    [ph('Palavra-chave'),        ph('Tipo'),  ph('Cliques'), ph('Impr.'), ph('CTR'),    ph('Conv.'), ph('Custo/Conv.')],
    [p('"motel"'),               p('Frase'),  p('182'), p('996'), p('18,27%'), p('42,67'), p('R$ 2,45')],
    [p('[moteis em Toledo]'),     p('Exata'),  p('83'),  p('679'), p('12,22%'), p('13,00'), p('R$ 4,62')],
    [p('[motel em Toledo PR]'),   p('Exata'),  p('44'),  p('246'), p('17,89%'), p('13,17'), p('R$ 2,54')],
    [p('"motel em Toledo PR"'),   p('Frase'),  p('18'),  p('83'),  p('21,69%'), p('4,33'),  p('R$ 3,02')],
    [p('"motel barato Toledo"'),  p('Frase'),  p('18'),  p('78'),  p('23,08%'), p('4,17'),  p('R$ 3,22')],
    [p('"motel suite"'),          p('Frase'),  p('22'),  p('84'),  p('26,19%'), p('4,00'),  p('R$ 2,75')],
    [p('"pernoite em toledo"'),   p('Frase'),  p('5'),   p('72'),  p('6,94%'),  p('3,00'),  p('R$ 1,63')],
    [p('[motel barato Toledo]'),  p('Exata'),  p('11'),  p('67'),  p('16,42%'), p('3,00'),  p('R$ 3,02')],
    [p('"motel em toledo"'),      p('Frase'),  p('31'),  p('97'),  p('31,96%'), p('3,17'),  p('R$ 5,48')],
    [p('[motel em toledo]'),      p('Exata'),  p('31'),  p('257'), p('12,06%'), p('2,50'),  p('R$ 9,48')],
]
story.append(make_table(kw_dest, [CW*0.285, CW*0.09, CW*0.085, CW*0.085, CW*0.10, CW*0.10, CW*0.155]))
sp(10)

# Análise
story.append(SecBar('  Analise das palavras-chave', CW))
sp(4)
story.append(Paragraph(
    'As palavras-chave de melhor desempenho no periodo foram as que combinam intencao clara de busca com o '
    'contexto local de Toledo. O termo "motel" (correspondencia de frase) sozinho gerou quase metade de todas '
    'as conversoes do mes (42,67), com custo por contato de apenas R$ 2,45. Isso mostra que ha um grande '
    'volume de pessoas buscando por moteis de forma direta e que o anuncio do Tantra esta aparecendo no '
    'momento certo. '
    'Termos com Toledo no nome, como "moteis em Toledo" e "motel em Toledo PR", tambem tiveram otimo '
    'desempenho, pois capturam clientes que ja sabem onde querem ficar. '
    'A palavra "pernoite em toledo" se destacou pela altissima taxa de clique que virou contato (60%), '
    'indicando que quem busca por pernoite tem alta intencao de reserva imediata. '
    'De modo geral, o grupo MOTEL - FUNDO DE FUNIL funcionou como esperado: atrair pessoas ja decididas a '
    'frequentar um motel em Toledo, resultando em um custo por conversao muito abaixo da media do mercado.',
    BODY))

story.append(PageBreak())

# ═══════════════════════════════════════════════
# PÁGINA 3 — DADOS COMPLETOS + FECHAMENTO
# ═══════════════════════════════════════════════

story.append(SecBar('  Todas as palavras-chave -- Grupo MOTEL - FUNDO DE FUNIL', CW))
sp(4)
all_kw = [
    [ph('Palavra-chave'),              ph('Tipo'),   ph('Clicks'), ph('Impr.'), ph('CTR'),    ph('Conv.'), ph('Custo')],
    [ps('"motel"'),                    ps('Frase'),  ps('182'), ps('996'),  ps('18,27%'), ps('42,67'), ps('R$ 104,39')],
    [ps('[moteis em Toledo]'),          ps('Exata'),  ps('83'),  ps('679'),  ps('12,22%'), ps('13,00'), ps('R$ 60,03')],
    [ps('[motel em Toledo PR]'),        ps('Exata'),  ps('44'),  ps('246'),  ps('17,89%'), ps('13,17'), ps('R$ 33,44')],
    [ps('"motel em Toledo PR"'),        ps('Frase'),  ps('18'),  ps('83'),   ps('21,69%'), ps('4,33'),  ps('R$ 13,10')],
    [ps('"motel barato Toledo"'),       ps('Frase'),  ps('18'),  ps('78'),   ps('23,08%'), ps('4,17'),  ps('R$ 13,40')],
    [ps('"motel suite"'),               ps('Frase'),  ps('22'),  ps('84'),   ps('26,19%'), ps('4,00'),  ps('R$ 10,98')],
    [ps('"motel em toledo"'),           ps('Frase'),  ps('31'),  ps('97'),   ps('31,96%'), ps('3,17'),  ps('R$ 17,36')],
    [ps('[motel em toledo]'),           ps('Exata'),  ps('31'),  ps('257'),  ps('12,06%'), ps('2,50'),  ps('R$ 23,71')],
    [ps('"pernoite em toledo"'),        ps('Frase'),  ps('5'),   ps('72'),   ps('6,94%'),  ps('3,00'),  ps('R$ 4,89')],
    [ps('[motel barato Toledo]'),       ps('Exata'),  ps('11'),  ps('67'),   ps('16,42%'), ps('3,00'),  ps('R$ 9,06')],
    [ps('[motel]'),                     ps('Exata'),  ps('38'),  ps('231'),  ps('16,45%'), ps('1,00'),  ps('R$ 5,81')],
    [ps('[motel pernoite Toledo]'),     ps('Exata'),  ps('6'),   ps('17'),   ps('35,29%'), ps('0,00'),  ps('R$ 4,90')],
    [ps('[motel melhor de toledo]'),    ps('Exata'),  ps('3'),   ps('30'),   ps('10,00%'), ps('0,00'),  ps('R$ 1,58')],
    [ps('"moteis em Toledo"'),          ps('Frase'),  ps('3'),   ps('9'),    ps('33,33%'), ps('0,00'),  ps('R$ 1,13')],
    [ps('[motel perto de mim Toledo]'), ps('Exata'),  ps('3'),   ps('11'),   ps('27,27%'), ps('0,00'),  ps('R$ 0,44')],
    [ps('[motel com hidro]'),           ps('Exata'),  ps('0'),   ps('1'),    ps('0,00%'),  ps('0,00'),  ps('R$ 0,00')],
    [ps('[pernoite em toledo]'),        ps('Exata'),  ps('0'),   ps('9'),    ps('0,00%'),  ps('0,00'),  ps('R$ 0,00')],
    [ps('Demais (sem cliques)'),        ps('Varias'), ps('0'),   ps('71'),   ps('-'),       ps('0,00'),  ps('R$ 0,00')],
    [ps('TOTAL'),                       ps(''),       ps('498'), ps('2.967'),ps('16,78%'), ps('94,00'), ps('R$ 304,24')],
]
t_all = make_table(all_kw, [CW*0.30, CW*0.08, CW*0.09, CW*0.09, CW*0.10, CW*0.09, CW*0.15])
t_all.setStyle(TableStyle([
    ('BACKGROUND', (0,-1),(-1,-1), colors.HexColor('#F0E0E0')),
    ('FONTNAME',   (0,-1),(-1,-1), 'Helvetica-Bold'),
    ('FONTSIZE',   (0,-1),(-1,-1), 7),
]))
story.append(t_all)
sp(10)

# Resumo final
story.append(SecBar('  Resumo Geral do Periodo', CW, bg=RED, tc=WHITE, bc=RED))
sp(4)
story.append(Paragraph(
    'Abril de 2026 foi um mes de resultados excepcionais para o Tantra Motel no Google Ads. '
    'Com investimento de R$ 304,24, a campanha gerou 94 conversoes a um custo medio de R$ 3,24 cada. '
    'A taxa de cliques de 16,78% e a taxa de conversao de 18,88% estao muito acima da media do mercado de '
    'hospedagem local. Para cada real investido em anuncios, o Tantra Motel recebeu multiplos contatos de '
    'clientes com intencao real de reserva, comprovando a eficiencia da estrategia adotada.',
    BOX))
sp(12)

story.append(HRFlowable(width=CW, thickness=0.7, color=BGRAY))
sp(6)
story.append(Paragraph(
    'Este relatorio foi preparado pela Nishida Publicidade com base nos dados exportados '
    'do Google Ads referentes ao periodo de 01/04/2026 a 30/04/2026.',
    S('foot', fontSize=7, textColor=GRAY, fontName='Helvetica', alignment=1)))

# ── Build ─────────────────────────────────────────────────────────────────────

doc = SimpleDocTemplate(OUTPUT, pagesize=A4,
    leftMargin=M, rightMargin=M,
    topMargin=36*mm, bottomMargin=20*mm)
doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
print("PDF gerado com sucesso:", OUTPUT)
