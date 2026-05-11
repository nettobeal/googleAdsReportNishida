"""
Gerador automatico do relatorio Google Ads (Nishida Publicidade).

Le os CSVs exportados pelo Google Ads em ./csvs/ e produz um PDF em ./output/.
Basta substituir os arquivos em csvs/ e rodar:

    python gerar_relatorio.py
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle as S
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.platypus import (
    Flowable, HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)

# ── Diretorios (script-relativos, funcionam em qualquer SO) ─────────────────
BASE_DIR   = Path(__file__).resolve().parent
CSV_DIR    = BASE_DIR / 'csvs'
ASSETS_DIR = BASE_DIR / 'assets'
OUTPUT_DIR = BASE_DIR / 'output'

# Nomes esperados dos CSVs exportados do Google Ads
CSV_KEYWORDS  = 'Relatório de palavras-chave da rede de pesquisa.csv'
CSV_ADGROUPS  = 'Relatório do grupo de anúncios.csv'
CSV_TIMESERIE = 'Gráfico_de_série_temporal'  # prefixo, datas variam

LOGO_NISHIDA = ASSETS_DIR / 'logo_nishida.png'
LOGO_CLIENTE = ASSETS_DIR / 'logo_cliente.png'

# ── Cores ───────────────────────────────────────────────────────────────────
RED   = colors.HexColor('#CC0000')
DARK  = colors.HexColor('#1A1A1A')
GRAY  = colors.HexColor('#666666')
LGRAY = colors.HexColor('#F5F5F5')
BGRAY = colors.HexColor('#DDDDDD')
WHITE = colors.white

# ── Pagina ──────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
M  = 18 * mm
CW = PAGE_W - 2 * M

# ── Estilos ─────────────────────────────────────────────────────────────────
BOX   = S('BX', fontSize=8.5, leading=14, textColor=DARK, fontName='Helvetica',
          borderColor=BGRAY, borderWidth=0.6,
          borderPadding=(10, 12, 12, 12), borderRadius=4, backColor=LGRAY)
BODY  = S('BD', fontSize=8.5, leading=13, textColor=DARK, fontName='Helvetica')
SMALL = S('SM', fontSize=7,   leading=10, textColor=GRAY, fontName='Helvetica')
PSEC  = S('SE', fontSize=10,  leading=14, textColor=RED,  fontName='Helvetica-Bold')
TITL  = S('TI', fontSize=16,  leading=20, textColor=DARK, fontName='Helvetica-Bold')
SUB   = S('SB', fontSize=9,   leading=13, textColor=GRAY, fontName='Helvetica')

# ═══════════════════════════════════════════════════════════════════════════
# 1) PARSING DOS CSVs
# ═══════════════════════════════════════════════════════════════════════════

MESES = {
    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'marco': 3, 'abril': 4,
    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9,
    'outubro': 10, 'novembro': 11, 'dezembro': 12,
}


def parse_num(s: str) -> float:
    """Converte numero em formato pt-BR ('1.289', '6,98', '11,50') para float."""
    if s is None:
        return 0.0
    s = s.strip().replace('%', '').replace('R$', '').strip()
    if s in ('', '--', '- -', '—'):
        return 0.0
    # remove separador de milhar (.) e troca decimal (,) por (.)
    return float(s.replace('.', '').replace(',', '.'))


def parse_period(line: str) -> tuple[date, date] | None:
    """Extrai (inicio, fim) de uma linha como '1 de abril de 2026 - 30 de abril de 2026'."""
    parts = re.split(r'\s*-\s*', line.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    return _pt_date(parts[0]), _pt_date(parts[1])


def _pt_date(txt: str) -> date | None:
    m = re.match(r'(\d{1,2})\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})', txt.strip(), re.IGNORECASE)
    if not m:
        return None
    d, mes_nome, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    mes = MESES.get(mes_nome)
    return date(y, mes, d) if mes else None


def short_match_type(tipo: str) -> str:
    """'Correspondência de frase' -> 'Frase'."""
    t = (tipo or '').lower()
    if 'exata' in t:  return 'Exata'
    if 'frase' in t:  return 'Frase'
    if 'ampla' in t or 'amplo' in t: return 'Ampla'
    return tipo or ''


@dataclass
class Keyword:
    keyword: str
    match_type: str
    clicks: int
    impressions: int
    ctr_pct: float        # 6.98 (significa 6,98%)
    avg_cpc: float
    cost: float
    conversions: float
    cost_per_conv: float
    conv_rate_pct: float


@dataclass
class AdGroup:
    name: str
    campaign: str
    impressions: int
    clicks: int
    cost: float
    conversions: float
    ctr_pct: float
    avg_cpc: float
    cost_per_conv: float
    conv_rate_pct: float


@dataclass
class Totals:
    impressions: int = 0
    clicks: int = 0
    cost: float = 0.0
    conversions: float = 0.0

    @property
    def ctr_pct(self) -> float:
        return (self.clicks / self.impressions * 100) if self.impressions else 0.0

    @property
    def avg_cpc(self) -> float:
        return (self.cost / self.clicks) if self.clicks else 0.0

    @property
    def conv_rate_pct(self) -> float:
        return (self.conversions / self.clicks * 100) if self.clicks else 0.0

    @property
    def cost_per_conv(self) -> float:
        return (self.cost / self.conversions) if self.conversions else 0.0


@dataclass
class ReportData:
    period_start: date | None = None
    period_end: date | None = None
    period_text: str = ''
    campaign: str = ''
    ad_group: str = ''
    keywords: list[Keyword] = field(default_factory=list)
    totals: Totals = field(default_factory=Totals)
    daily_impressions: list[tuple[str, int]] = field(default_factory=list)


def load_keywords(path: Path) -> tuple[list[Keyword], str]:
    """Le o CSV de palavras-chave. Retorna (lista, periodo_texto)."""
    period_text = ''
    rows: list[Keyword] = []
    with path.open(encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        _ = next(reader, None)                       # titulo do relatorio
        period_row = next(reader, None)              # periodo
        if period_row:
            period_text = period_row[0]
        header = next(reader, None)                  # cabecalho
        if not header:
            return rows, period_text

        idx = {name: i for i, name in enumerate(header)}

        def col(row: list[str], name: str) -> str:
            return row[idx[name]] if name in idx and idx[name] < len(row) else ''

        for row in reader:
            if not row or not any(row):
                continue
            kw = col(row, 'Palavra-chave')
            if not kw or kw.startswith('Total:'):
                continue
            # Linhas de totais aparecem com a 3a coluna comecando por "Total:"
            if any((c or '').startswith('Total:') for c in row[:3]):
                continue
            rows.append(Keyword(
                keyword       = kw,
                match_type    = short_match_type(col(row, 'Tipo de corresp.')),
                clicks        = int(parse_num(col(row, 'Cliques'))),
                impressions   = int(parse_num(col(row, 'Impr.'))),
                ctr_pct       = parse_num(col(row, 'CTR')),
                avg_cpc       = parse_num(col(row, 'CPC méd.')),
                cost          = parse_num(col(row, 'Custo')),
                conversions   = parse_num(col(row, 'Conversões')),
                cost_per_conv = parse_num(col(row, 'Custo / conv.')),
                conv_rate_pct = parse_num(col(row, 'Taxa de conv.')),
            ))
    return rows, period_text


def load_adgroups(path: Path) -> list[AdGroup]:
    """Le o CSV de grupos de anuncios e retorna os grupos com impressoes > 0."""
    groups: list[AdGroup] = []
    with path.open(encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        _ = next(reader, None)
        _ = next(reader, None)
        header = next(reader, None)
        if not header:
            return groups
        idx = {name: i for i, name in enumerate(header)}

        def col(row: list[str], name: str) -> str:
            return row[idx[name]] if name in idx and idx[name] < len(row) else ''

        for row in reader:
            if not row or not any(row):
                continue
            name = col(row, 'Grupo de anúncios')
            if not name or (row[0] or '').startswith('Total'):
                continue
            impr = int(parse_num(col(row, 'Impr.')))
            if impr <= 0:
                continue
            groups.append(AdGroup(
                name          = name,
                campaign      = col(row, 'Campanha'),
                impressions   = impr,
                clicks        = int(parse_num(col(row, 'Cliques'))),
                cost          = parse_num(col(row, 'Custo')),
                conversions   = parse_num(col(row, 'Conversões')),
                ctr_pct       = parse_num(col(row, 'Taxa de interação')),
                avg_cpc       = parse_num(col(row, 'CPC méd.')),
                cost_per_conv = parse_num(col(row, 'Custo / conv.')),
                conv_rate_pct = parse_num(col(row, 'Taxa de conv.')),
            ))
    return groups


def load_timeseries(path: Path) -> list[tuple[str, int]]:
    """Le o CSV de serie temporal. Retorna lista (label_dia, impressoes)."""
    out: list[tuple[str, int]] = []
    with path.open(encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        next(reader, None)  # cabecalho 'Data,Impr.'
        for row in reader:
            if not row or len(row) < 2:
                continue
            # 'qua., 1 de abr. de 2026' -> '01/04'
            m = re.search(r'(\d{1,2})\s+de\s+([A-Za-zÀ-ÿ]+)', row[0])
            if m:
                d = int(m.group(1))
                mes_pref = m.group(2).lower().strip('.')
                # mapeia abreviacao -> numero
                meses_abrev = {'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
                               'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12}
                mes_num = meses_abrev.get(mes_pref[:3], 0)
                label = f"{d:02d}/{mes_num:02d}"
            else:
                label = row[0]
            out.append((label, int(parse_num(row[1]))))
    return out


def find_timeseries_csv() -> Path | None:
    for p in CSV_DIR.glob(f'{CSV_TIMESERIE}*.csv'):
        return p
    return None


def load_report_data() -> ReportData:
    data = ReportData()

    kw_path = CSV_DIR / CSV_KEYWORDS
    if kw_path.exists():
        data.keywords, period_text = load_keywords(kw_path)
        rng = parse_period(period_text)
        if rng:
            data.period_start, data.period_end = rng

    ag_path = CSV_DIR / CSV_ADGROUPS
    if ag_path.exists():
        ad_groups = load_adgroups(ag_path)
        if ad_groups:
            # grupo de maior impressao como referencia
            ad_groups.sort(key=lambda g: g.impressions, reverse=True)
            top = ad_groups[0]
            data.ad_group = top.name
            data.campaign = top.campaign

    ts_path = find_timeseries_csv()
    if ts_path:
        data.daily_impressions = load_timeseries(ts_path)

    # totais agregados a partir das palavras-chave
    for k in data.keywords:
        data.totals.impressions += k.impressions
        data.totals.clicks      += k.clicks
        data.totals.cost        += k.cost
        data.totals.conversions += k.conversions

    # texto do periodo
    if data.period_start and data.period_end:
        data.period_text = (
            f"{data.period_start.strftime('%d/%m/%Y')} a "
            f"{data.period_end.strftime('%d/%m/%Y')}"
        )
    return data


# ═══════════════════════════════════════════════════════════════════════════
# 2) FORMATACAO E AVALIACOES
# ═══════════════════════════════════════════════════════════════════════════

def fmt_int(n: float | int) -> str:
    return f"{int(round(n)):,}".replace(',', '.')

def fmt_money(n: float, decimals: int = 2) -> str:
    s = f"{n:,.{decimals}f}"
    # troca separador americano por pt-BR
    return 'R$ ' + s.replace(',', '#').replace('.', ',').replace('#', '.')

def fmt_money_short(n: float) -> str:
    return fmt_money(n, decimals=0)

def fmt_pct(n: float) -> str:
    return f"{n:.2f}%".replace('.', ',')

def fmt_dec(n: float, decimals: int = 2) -> str:
    return f"{n:.{decimals}f}".replace('.', ',')


def assess_ctr(pct: float) -> str:
    if pct >= 5:  return 'Acima da média'
    if pct >= 3:  return 'Dentro da média'
    return 'Abaixo da média'

def assess_cpc(value: float) -> str:
    if value == 0:           return '-'
    if value <= 2:            return 'Dentro da média'
    if value <= 5:            return 'Acima da média'
    return 'Muito acima da média'

def assess_conv_rate(pct: float) -> str:
    if pct >= 4:  return 'Acima da média'
    if pct >= 2:  return 'Dentro da média'
    if pct > 0:   return 'Abaixo da média'
    return 'Sem conversões'

def assess_cost_per_conv(value: float, has_conv: bool) -> str:
    if not has_conv:  return 'Sem conversões'
    if value <= 10:   return 'Excelente'
    if value <= 30:   return 'Dentro da média'
    return 'Acima da média'


# ═══════════════════════════════════════════════════════════════════════════
# 3) FLOWABLES CUSTOMIZADOS
# ═══════════════════════════════════════════════════════════════════════════

class SecBar(Flowable):
    PAD = 6

    def __init__(self, txt, w, bg=LGRAY, tc=RED, bc=RED):
        self.txt, self.w, self.bg, self.tc, self.bc = txt, w, bg, tc, bc

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


class Cards4(Flowable):
    def __init__(self, cards, w):
        self.cards, self.w, self.h = cards, w, 68

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
            if hi:
                c.setFillColor(RED)
                c.roundRect(x, self.h - 5, cw, 5, 4, fill=1, stroke=0)
                c.rect(x, self.h - 8, cw, 4, fill=1, stroke=0)
            c.setFillColor(GRAY); c.setFont('Helvetica', 7)
            c.drawString(x + 7, self.h - 15, lbl)
            c.setFillColor(DARK); c.setFont('Helvetica-Bold', 17)
            c.drawString(x + 7, self.h - 36, val)
            c.setFillColor(GRAY); c.setFont('Helvetica', 7)
            c.drawString(x + 7, self.h - 50, sub)


class BigBox(Flowable):
    def __init__(self, val, lbl, txt, w, h=90):
        self.val, self.lbl, self.txt, self.w, self.h = val, lbl, txt, w, h

    def wrap(self, *_):
        return self.w, self.h

    def draw(self):
        c, lw = self.canv, 110
        c.setFillColor(LGRAY); c.setStrokeColor(BGRAY); c.setLineWidth(0.8)
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


class DailyChart(Flowable):
    """Mini grafico de barras das impressoes diarias."""

    def __init__(self, series: list[tuple[str, int]], w, h=80):
        self.series, self.w, self.h = series, w, h

    def wrap(self, *_):
        return self.w, self.h

    def draw(self):
        if not self.series:
            return
        c = self.canv
        n = len(self.series)
        max_val = max((v for _, v in self.series), default=1) or 1
        chart_h = self.h - 22
        slot_w  = (self.w - 12) / n
        bar_w   = max(2.0, slot_w * 0.75)

        # eixo base
        c.setStrokeColor(BGRAY); c.setLineWidth(0.4)
        c.line(6, 18, self.w - 6, 18)

        for i, (label, val) in enumerate(self.series):
            x = 6 + i * slot_w + (slot_w - bar_w) / 2
            bar_h = (val / max_val) * chart_h
            c.setFillColor(RED if val > 0 else BGRAY)
            c.rect(x, 18, bar_w, bar_h, fill=1, stroke=0)
            # rotulo: dia a cada 3 dias ou no ultimo
            if i % 3 == 0 or i == n - 1:
                c.setFillColor(GRAY); c.setFont('Helvetica', 5.5)
                c.drawCentredString(x + bar_w / 2, 9, label)
            # valor no topo de barras altas
            if val == max_val and val > 0:
                c.setFillColor(DARK); c.setFont('Helvetica-Bold', 6)
                c.drawCentredString(x + bar_w / 2, 19 + bar_h + 2, str(val))


# ═══════════════════════════════════════════════════════════════════════════
# 4) HELPERS DE TABELA
# ═══════════════════════════════════════════════════════════════════════════

def make_table(rows, widths):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1,  0), RED),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [LGRAY, WHITE]),
        ('GRID',          (0, 0), (-1, -1), 0.4, BGRAY),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
        ('FONTNAME',      (0, 0), (-1,  0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 7),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TEXTCOLOR',     (0, 0), (-1,  0), WHITE),
    ]))
    return t


def ph(txt): return Paragraph(f'<b>{txt}</b>', S('ph', fontSize=7, textColor=WHITE, fontName='Helvetica-Bold'))
def p(txt):  return Paragraph(str(txt),        S('p',  fontSize=7, textColor=DARK,  fontName='Helvetica', leading=9))
def ps(txt): return Paragraph(str(txt),        S('ps', fontSize=6.5, textColor=DARK, fontName='Helvetica', leading=8))


# ═══════════════════════════════════════════════════════════════════════════
# 5) HEADER / FOOTER
# ═══════════════════════════════════════════════════════════════════════════

def make_page_drawer(generated_on: str):
    def draw_page(canv, doc):
        canv.saveState()
        if LOGO_NISHIDA.exists():
            canv.drawImage(str(LOGO_NISHIDA),
                           M, PAGE_H - 28 * mm,
                           width=42 * mm, height=10 * mm,
                           preserveAspectRatio=True, anchor='sw', mask='auto')
        if LOGO_CLIENTE.exists():
            canv.drawImage(str(LOGO_CLIENTE),
                           PAGE_W - M - 22 * mm, PAGE_H - 31 * mm,
                           width=22 * mm, height=22 * mm,
                           preserveAspectRatio=True, anchor='sw', mask='auto')
        canv.setStrokeColor(BGRAY); canv.setLineWidth(0.5)
        canv.line(M, PAGE_H - 32 * mm, PAGE_W - M, PAGE_H - 32 * mm)
        canv.line(M, 13 * mm, PAGE_W - M, 13 * mm)
        canv.setFont('Helvetica', 7.5); canv.setFillColor(GRAY)
        canv.drawString(M, 8 * mm, 'Nishida Publicidade')
        canv.drawRightString(PAGE_W - M, 8 * mm, f'Relatorio gerado em {generated_on}')
        canv.restoreState()
    return draw_page


# ═══════════════════════════════════════════════════════════════════════════
# 6) MONTAGEM DA STORY
# ═══════════════════════════════════════════════════════════════════════════

def build_story(d: ReportData, generated_on: str) -> list:
    story: list = []
    sp = lambda n=6: story.append(Spacer(1, n))

    t = d.totals
    has_conv = t.conversions > 0

    # ── Pagina 1 ─────────────────────────────────────────────────────────────
    story.append(Paragraph('Relatorio de Campanha - Google Ads', TITL))
    sp(4)
    campaign_label = d.campaign or '—'
    story.append(Paragraph(
        f'Periodo: {d.period_text or "—"}   |   Gerado em: {generated_on}   |   '
        f'Campanha: {campaign_label}', SUB))
    sp(6)
    story.append(HRFlowable(width=CW, thickness=1.5, color=RED, spaceAfter=10))

    # Resumo
    story.append(SecBar('  Resumo do Periodo', CW))
    sp(4)
    conv_phrase = (
        f"e {fmt_dec(t.conversions)} conversoes registradas (custo medio por "
        f"conversao de {fmt_money(t.cost_per_conv)})"
        if has_conv else
        "sem conversoes registradas no periodo"
    )
    story.append(Paragraph(
        f'No periodo de {d.period_text or "—"}, a campanha entregou '
        f'{fmt_int(t.impressions)} exibicoes e gerou {fmt_int(t.clicks)} cliques, '
        f'resultando em CTR de {fmt_pct(t.ctr_pct)}. O investimento total foi de '
        f'{fmt_money(t.cost)}, com CPC medio de {fmt_money(t.avg_cpc)} {conv_phrase}.',
        BOX))
    sp(10)

    # Como funciona
    story.append(SecBar('  Como o Google Ads funciona', CW))
    sp(4)
    story.append(Paragraph(
        'Quando alguem digita no Google um termo relacionado ao negocio, o anuncio aparece nos '
        'resultados de pesquisa. O anunciante paga apenas quando alguem clica no anuncio. A '
        'campanha e configurada para aparecer somente para pessoas com intencao real de '
        'contratar, otimizando o retorno do investimento.',
        BODY))
    sp(10)

    # Benchmark
    story.append(SecBar('  Cliente vs. media do mercado', CW))
    sp(4)
    bench_rows = [
        [ph('Metrica'),              ph('Resultado'),                ph('Media do Mercado'),  ph('Avaliacao')],
        [p('CTR (taxa de cliques)'), p(fmt_pct(t.ctr_pct)),          p('3 a 5%'),             p(assess_ctr(t.ctr_pct))],
        [p('CPC medio'),             p(fmt_money(t.avg_cpc)),        p('R$ 0,50 a R$ 2,00'),  p(assess_cpc(t.avg_cpc))],
        [p('Taxa de conversao'),     p(fmt_pct(t.conv_rate_pct)),    p('2 a 4%'),             p(assess_conv_rate(t.conv_rate_pct))],
        [p('Custo por conversao'),   p(fmt_money(t.cost_per_conv) if has_conv else '—'),
                                     p('R$ 10 a R$ 30'),             p(assess_cost_per_conv(t.cost_per_conv, has_conv))],
    ]
    story.append(make_table(bench_rows, [CW * 0.28, CW * 0.22, CW * 0.28, CW * 0.22]))
    sp(10)

    # Cards
    story.append(Paragraph('Resultados consolidados do periodo', PSEC))
    sp(5)
    story.append(Cards4([
        ('Impressoes', fmt_int(t.impressions), 'exibicoes no periodo', False),
        ('Cliques',    fmt_int(t.clicks),       'acessos gerados',      True),
        ('CTR',        fmt_pct(t.ctr_pct),      'taxa de cliques',      True),
        ('Conversoes', fmt_dec(t.conversions, 0 if t.conversions == int(t.conversions) else 2),
                                                'contatos gerados',    has_conv),
    ], CW))
    sp(6)
    story.append(Cards4([
        ('Custo Total',     fmt_money_short(t.cost),   'investimento no periodo',     False),
        ('CPC Medio',       fmt_money(t.avg_cpc),      'custo por clique',            False),
        ('Taxa de Conv.',   fmt_pct(t.conv_rate_pct),  'cliques que viraram contato', has_conv),
        ('Custo/Conversao', fmt_money(t.cost_per_conv) if has_conv else '—',
                                                       'custo por contato',           has_conv),
    ], CW))

    story.append(PageBreak())

    # ── Pagina 2 ─────────────────────────────────────────────────────────────
    story.append(SecBar('  Grupo de Anuncios', CW, bg=RED, tc=WHITE, bc=RED))
    sp(4)
    story.append(Paragraph(
        f'Campanha: {campaign_label}   |   Grupo: {d.ad_group or "—"}',
        SMALL))
    sp(8)

    story.append(Cards4([
        ('Cliques',       fmt_int(t.clicks),        f'grupo {d.ad_group or ""}'.strip(), False),
        ('Impressoes',    fmt_int(t.impressions),   'no periodo',                        False),
        ('Taxa de Conv.', fmt_pct(t.conv_rate_pct), assess_conv_rate(t.conv_rate_pct),   has_conv),
        ('Custo/Conv.',   fmt_money(t.cost_per_conv) if has_conv else '—',
                                                    'por contato gerado',                has_conv),
    ], CW))
    sp(10)

    # Destaque
    if has_conv:
        story.append(BigBox(
            fmt_money(t.cost_per_conv),
            'custo por conversao (contato gerado)',
            f'Cada contato gerado pela campanha custou {fmt_money(t.cost_per_conv)}. '
            f'Foram {fmt_dec(t.conversions)} conversoes para um investimento de {fmt_money(t.cost)}. '
            f'A media do mercado gira em torno de R$ 10 a R$ 30 por conversao.',
            CW, h=95))
    else:
        story.append(BigBox(
            fmt_int(t.clicks),
            'cliques no periodo',
            f'A campanha gerou {fmt_int(t.clicks)} cliques sobre {fmt_int(t.impressions)} exibicoes '
            f'(CTR de {fmt_pct(t.ctr_pct)}), porem nao foram registradas conversoes no periodo. '
            f'Recomenda-se revisar o rastreamento de conversoes (tags / pixels) e a configuracao das '
            f'metas para que as acoes valiosas sejam contabilizadas corretamente.',
            CW, h=95))
    sp(10)

    # Daily chart
    if d.daily_impressions:
        story.append(SecBar('  Impressoes diarias no periodo', CW))
        sp(4)
        story.append(DailyChart(d.daily_impressions, CW, h=82))
        sp(8)

    # Top palavras-chave (por cliques)
    story.append(SecBar('  Palavras-chave com maior desempenho', CW))
    sp(4)
    top_kw = sorted(d.keywords, key=lambda k: (k.conversions, k.clicks, k.impressions), reverse=True)[:10]
    rows_top = [[ph('Palavra-chave'), ph('Tipo'), ph('Cliques'), ph('Impr.'),
                 ph('CTR'), ph('Conv.'), ph('Custo/Conv.')]]
    for k in top_kw:
        rows_top.append([
            p(k.keyword), p(k.match_type), p(fmt_int(k.clicks)), p(fmt_int(k.impressions)),
            p(fmt_pct(k.ctr_pct)),
            p(fmt_dec(k.conversions)),
            p(fmt_money(k.cost_per_conv) if k.conversions > 0 else '—'),
        ])
    story.append(make_table(rows_top, [CW * 0.285, CW * 0.09, CW * 0.085, CW * 0.085,
                                       CW * 0.10, CW * 0.10, CW * 0.155]))
    sp(10)

    # Analise
    story.append(SecBar('  Analise das palavras-chave', CW))
    sp(4)
    if top_kw:
        top1 = top_kw[0]
        share = (top1.clicks / t.clicks * 100) if t.clicks else 0
        if has_conv and top1.conversions > 0:
            analise = (
                f"A palavra-chave de melhor desempenho foi <b>{top1.keyword}</b> "
                f"({top1.match_type}), responsavel por {fmt_dec(top1.conversions)} conversoes a um "
                f"custo de {fmt_money(top1.cost_per_conv)} por contato. "
                f"No total, o grupo {d.ad_group or 'analisado'} concentrou {fmt_int(t.clicks)} cliques "
                f"sobre {fmt_int(t.impressions)} impressoes, com CTR de {fmt_pct(t.ctr_pct)}."
            )
        else:
            analise = (
                f"A palavra-chave que mais gerou trafego foi <b>{top1.keyword}</b> "
                f"({top1.match_type}), com {fmt_int(top1.clicks)} cliques "
                f"({fmt_pct(share)} do total). "
                f"Embora a campanha tenha gerado {fmt_int(t.clicks)} cliques no periodo, nao houve "
                f"conversoes contabilizadas — vale revisar o rastreamento e/ou a oferta da pagina "
                f"de destino para transformar cliques em contatos."
            )
    else:
        analise = "Nao foram encontradas palavras-chave com dados de desempenho no periodo."
    story.append(Paragraph(analise, BODY))

    story.append(PageBreak())

    # ── Pagina 3 ─────────────────────────────────────────────────────────────
    story.append(SecBar(f'  Todas as palavras-chave -- {d.ad_group or "Grupo"}', CW))
    sp(4)

    # Mostra apenas palavras-chave com impressoes; demais sao agregadas em 1 linha.
    active = [k for k in d.keywords if k.impressions > 0]
    inactive = [k for k in d.keywords if k.impressions == 0]
    active.sort(key=lambda k: (k.conversions, k.clicks, k.impressions), reverse=True)

    rows_all = [[ph('Palavra-chave'), ph('Tipo'), ph('Clicks'), ph('Impr.'),
                 ph('CTR'), ph('Conv.'), ph('Custo')]]
    for k in active:
        rows_all.append([
            ps(k.keyword), ps(k.match_type),
            ps(fmt_int(k.clicks)), ps(fmt_int(k.impressions)),
            ps(fmt_pct(k.ctr_pct) if k.impressions else '-'),
            ps(fmt_dec(k.conversions)),
            ps(fmt_money(k.cost)),
        ])
    if inactive:
        rows_all.append([
            ps(f'Demais ({len(inactive)} sem impressoes)'), ps('Varias'),
            ps('0'), ps('0'), ps('-'), ps('0,00'), ps(fmt_money(0)),
        ])
    rows_all.append([
        ps('TOTAL'), ps(''),
        ps(fmt_int(t.clicks)), ps(fmt_int(t.impressions)),
        ps(fmt_pct(t.ctr_pct)),
        ps(fmt_dec(t.conversions)),
        ps(fmt_money(t.cost)),
    ])
    t_all = make_table(rows_all, [CW * 0.30, CW * 0.08, CW * 0.09, CW * 0.09,
                                  CW * 0.10, CW * 0.09, CW * 0.15])
    t_all.setStyle(TableStyle([
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F0E0E0')),
        ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, -1), (-1, -1), 7),
    ]))
    story.append(t_all)
    sp(10)

    # Fechamento
    story.append(SecBar('  Resumo Geral do Periodo', CW, bg=RED, tc=WHITE, bc=RED))
    sp(4)
    if has_conv:
        fechamento = (
            f"No periodo de {d.period_text}, a campanha investiu {fmt_money(t.cost)} e gerou "
            f"{fmt_dec(t.conversions)} conversoes a um custo medio de {fmt_money(t.cost_per_conv)} cada. "
            f"O CTR de {fmt_pct(t.ctr_pct)} e a taxa de conversao de {fmt_pct(t.conv_rate_pct)} indicam "
            f"o desempenho do grupo {d.ad_group or 'avaliado'}."
        )
    else:
        fechamento = (
            f"No periodo de {d.period_text}, a campanha investiu {fmt_money(t.cost)} e gerou "
            f"{fmt_int(t.clicks)} cliques sobre {fmt_int(t.impressions)} exibicoes "
            f"(CTR de {fmt_pct(t.ctr_pct)}, CPC medio de {fmt_money(t.avg_cpc)}). "
            f"Nao foram registradas conversoes no periodo: recomenda-se uma revisao do rastreamento "
            f"de conversoes e da pagina de destino para que os cliques se traduzam em contatos."
        )
    story.append(Paragraph(fechamento, BOX))
    sp(12)
    story.append(HRFlowable(width=CW, thickness=0.7, color=BGRAY))
    sp(6)
    story.append(Paragraph(
        f'Este relatorio foi preparado pela Nishida Publicidade com base nos dados exportados '
        f'do Google Ads referentes ao periodo de {d.period_text or "—"}.',
        S('foot', fontSize=7, textColor=GRAY, fontName='Helvetica', alignment=1)))
    return story


# ═══════════════════════════════════════════════════════════════════════════
# 7) ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    if not CSV_DIR.exists():
        print(f"[erro] pasta de CSVs nao encontrada: {CSV_DIR}", file=sys.stderr)
        return 1

    data = load_report_data()
    if not data.keywords:
        print(f"[erro] nenhuma palavra-chave lida de {CSV_DIR / CSV_KEYWORDS}",
              file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()
    generated_on = today.strftime('%d/%m/%Y')

    suffix = ''
    if data.period_start and data.period_end:
        suffix = f"_{data.period_start.strftime('%Y%m%d')}-{data.period_end.strftime('%Y%m%d')}"
    output_path = OUTPUT_DIR / f'Relatorio_GoogleAds{suffix}.pdf'

    story = build_story(data, generated_on)
    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=M, rightMargin=M,
        topMargin=36 * mm, bottomMargin=20 * mm,
    )
    draw = make_page_drawer(generated_on)
    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    print(f"PDF gerado com sucesso: {output_path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
