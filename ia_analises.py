"""
Geracao das analises do relatorio usando a Claude API (Anthropic).

Como funciona:
- Le as instrucoes em `instrucoes_ia.md` (editavel pelo usuario)
- Monta o contexto com os dados da campanha
- Pede ao Claude que devolva 3 textos em JSON (resumo, analise, fechamento)
- Se nao houver `ANTHROPIC_API_KEY` no ambiente, retorna None
  (o gerador de PDF usa entao os textos parametrizados padrao)

Modelo: claude-opus-4-7 com adaptive thinking.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    import anthropic
    from pydantic import BaseModel
    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False


BASE_DIR = Path(__file__).resolve().parent
INSTRUCOES_PATH = BASE_DIR / 'instrucoes_ia.md'

# Fallback caso o arquivo de instrucoes nao exista
INSTRUCOES_DEFAULT = """\
Voce e um analista de marketing digital da Nishida Publicidade. Escreva em
portugues brasileiro, tom profissional mas acessivel, frases curtas e diretas,
sem jargao. Use APENAS os numeros fornecidos. Quando houver problemas (ex.: 0
conversoes), aponte com honestidade. Gere tres textos: resumo_periodo (3-4
frases), analise_keywords (4-6 frases) e fechamento (3-4 frases).
"""


@dataclass
class AnaliseIA:
    """Textos gerados pela IA para encaixar no PDF."""
    resumo_periodo: str
    analise_keywords: str
    fechamento: str


if _HAS_DEPS:
    class _RespostaIA(BaseModel):
        """Schema do JSON que o Claude deve devolver."""
        resumo_periodo: str
        analise_keywords: str
        fechamento: str


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_instrucoes() -> str:
    if INSTRUCOES_PATH.exists():
        return INSTRUCOES_PATH.read_text(encoding='utf-8')
    return INSTRUCOES_DEFAULT


def _build_contexto(data) -> str:
    """Formata os dados da campanha em texto plano para o prompt."""
    t = data.totals
    has_conv = t.conversions > 0

    def br_int(n):
        return f"{int(round(n)):,}".replace(',', '.')

    def br_money(n):
        return f"R$ {n:,.2f}".replace(',', '#').replace('.', ',').replace('#', '.')

    lines = [
        f"Cliente: {data.client_name or '-'}",
        f"Periodo: {data.period_text or '-'}",
        f"Campanha: {data.campaign or '-'}",
        f"Grupo de anuncios: {data.ad_group or '-'}",
        "",
        "Totais do periodo:",
        f"- Impressoes: {br_int(t.impressions)}",
        f"- Cliques: {br_int(t.clicks)}",
        f"- CTR: {t.ctr_pct:.2f}%".replace('.', ','),
        f"- CPC medio: {br_money(t.avg_cpc)}",
        f"- Investimento total: {br_money(t.cost)}",
        f"- Conversoes: {t.conversions:.2f}".replace('.', ','),
        f"- Taxa de conversao: {t.conv_rate_pct:.2f}%".replace('.', ','),
    ]
    if has_conv:
        lines.append(f"- Custo por conversao: {br_money(t.cost_per_conv)}")
    else:
        lines.append("- Custo por conversao: N/A (sem conversoes registradas)")

    lines += [
        "",
        "Top palavras-chave por desempenho (ordenadas por conversoes / cliques):",
    ]

    top_kw = sorted(
        (k for k in data.keywords if k.impressions > 0),
        key=lambda k: (k.conversions, k.clicks, k.impressions),
        reverse=True,
    )[:10]
    if not top_kw:
        lines.append("- (nenhuma palavra-chave com impressoes no periodo)")
    for k in top_kw:
        custo_conv = br_money(k.cost_per_conv) if k.conversions > 0 else 'sem conv'
        lines.append(
            f"- '{k.keyword}' ({k.match_type}): {k.clicks} cliques, "
            f"{k.impressions} impr, CTR {k.ctr_pct:.2f}%, "
            f"{k.conversions:.2f} conv, custo {br_money(k.cost)}, "
            f"custo/conv {custo_conv}".replace('.', ',')
        )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def gerar_analises(data) -> AnaliseIA | None:
    """
    Gera os 3 textos via Claude API.

    Retorna None (silenciosamente) quando:
    - pacotes anthropic / pydantic nao estao instalados
    - ANTHROPIC_API_KEY nao esta no ambiente
    - a chamada falha por qualquer motivo

    Nesses casos, o gerador de PDF cai para os textos parametrizados padrao.
    """
    if not _HAS_DEPS:
        print("[ia] anthropic/pydantic nao instalados - usando textos padrao")
        return None

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("[ia] ANTHROPIC_API_KEY nao definido - usando textos padrao")
        return None

    instrucoes = _load_instrucoes()
    contexto = _build_contexto(data)

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.parse(
            model="claude-opus-4-7",
            max_tokens=4000,
            thinking={"type": "adaptive"},
            system=instrucoes,
            messages=[{
                "role": "user",
                "content": (
                    "Analise os dados abaixo e devolva os 3 textos em JSON "
                    "conforme as instrucoes do sistema:\n\n"
                    f"{contexto}"
                ),
            }],
            output_format=_RespostaIA,
        )
    except anthropic.APIError as e:
        print(f"[ia] erro da Claude API ({type(e).__name__}): {e} - usando textos padrao")
        return None
    except Exception as e:
        print(f"[ia] falha inesperada: {e} - usando textos padrao")
        return None

    parsed = response.parsed_output
    if parsed is None:
        print("[ia] resposta sem parsed_output - usando textos padrao")
        return None

    print(f"[ia] analises geradas (input: {response.usage.input_tokens} / "
          f"output: {response.usage.output_tokens} tokens)")
    return AnaliseIA(
        resumo_periodo=parsed.resumo_periodo.strip(),
        analise_keywords=parsed.analise_keywords.strip(),
        fechamento=parsed.fechamento.strip(),
    )
