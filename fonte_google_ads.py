"""
Fonte de dados: Google Ads API.

Credenciais (qualquer um dos dois caminhos):

  1. Variaveis de ambiente:
       GOOGLE_ADS_DEVELOPER_TOKEN
       GOOGLE_ADS_CLIENT_ID
       GOOGLE_ADS_CLIENT_SECRET
       GOOGLE_ADS_REFRESH_TOKEN
       GOOGLE_ADS_LOGIN_CUSTOMER_ID    (opcional - so para contas gerenciador / MCC)

  2. Arquivo `google-ads.yaml` no diretorio atual ou em ~/.

Sempre obrigatorio:
       GOOGLE_ADS_CUSTOMER_ID          (id da conta a ser consultada, sem tracos)

Periodo (opcional - default: mes calendario anterior):
       REPORT_START  (YYYY-MM-DD)
       REPORT_END    (YYYY-MM-DD)
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    _HAS_SDK = True
except ImportError:
    GoogleAdsClient = None  # type: ignore
    GoogleAdsException = Exception  # type: ignore
    _HAS_SDK = False

from dados import AdGroup, Keyword, ReportData, Totals  # noqa: F401 (AdGroup reuse)


YAML_LOCATIONS = [
    Path.cwd() / 'google-ads.yaml',
    Path.home() / 'google-ads.yaml',
]

ENV_KEYS = [
    'GOOGLE_ADS_DEVELOPER_TOKEN',
    'GOOGLE_ADS_CLIENT_ID',
    'GOOGLE_ADS_CLIENT_SECRET',
    'GOOGLE_ADS_REFRESH_TOKEN',
]

CUSTOMER_PREFIX = 'GOOGLE_ADS_CUSTOMER_ID_'

_MATCH_TYPE_MAP = {
    'EXACT':       'Exata',
    'PHRASE':      'Frase',
    'BROAD':       'Ampla',
    'UNSPECIFIED': '',
    'UNKNOWN':     '',
}


# ─────────────────────────────────────────────────────────────────────────────
# Disponibilidade
# ─────────────────────────────────────────────────────────────────────────────

def list_clients() -> dict[str, str]:
    """
    Descobre todos os clientes configurados via env vars
    GOOGLE_ADS_CUSTOMER_ID_<NOME>=<id>. Retorna {NOME: customer_id}.
    """
    out: dict[str, str] = {}
    for key, val in os.environ.items():
        if not key.startswith(CUSTOMER_PREFIX) or not val:
            continue
        nome = key[len(CUSTOMER_PREFIX):]
        out[nome] = val.replace('-', '').strip()
    return out


def credentials_available() -> bool:
    """Retorna True se da pra tentar usar a Google Ads API."""
    if not _HAS_SDK:
        return False
    # Precisa ter pelo menos um cliente OU o GOOGLE_ADS_CUSTOMER_ID legado
    if not os.environ.get('GOOGLE_ADS_CUSTOMER_ID') and not list_clients():
        return False
    # credenciais via env?
    if all(os.environ.get(k) for k in ENV_KEYS):
        return True
    # ou via yaml?
    return any(p.exists() for p in YAML_LOCATIONS)


def _load_client():
    # use_proto_plus precisa estar definido ou o SDK reclama
    os.environ.setdefault('GOOGLE_ADS_USE_PROTO_PLUS', 'True')

    if all(os.environ.get(k) for k in ENV_KEYS):
        return GoogleAdsClient.load_from_env()
    for p in YAML_LOCATIONS:
        if p.exists():
            return GoogleAdsClient.load_from_storage(str(p))
    raise RuntimeError(
        "Nenhuma credencial Google Ads encontrada. "
        "Defina as variaveis GOOGLE_ADS_* ou crie um google-ads.yaml."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Periodo
# ─────────────────────────────────────────────────────────────────────────────

def _default_period() -> tuple[date, date]:
    """Mes calendario anterior."""
    today = date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev, last_prev


def _resolve_period() -> tuple[date, date]:
    start_env = os.environ.get('REPORT_START')
    end_env = os.environ.get('REPORT_END')
    if start_env and end_env:
        return date.fromisoformat(start_env), date.fromisoformat(end_env)
    return _default_period()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _format_kw(text: str, match_type_name: str) -> str:
    """Formato visual usado no relatorio: [exata], \"frase\", ampla."""
    if match_type_name == 'EXACT':
        return f'[{text}]'
    if match_type_name == 'PHRASE':
        return f'"{text}"'
    return text


def resolve_client(requested: str | None = None) -> tuple[str, str]:
    """
    Decide qual cliente usar e retorna (nome, customer_id).

    Ordem de prioridade:
    1. `requested` (vindo de --client na CLI)
    2. env var REPORT_CLIENT
    3. env var GOOGLE_ADS_CUSTOMER_ID (compat: cliente unico anonimo)
    4. prompt interativo listando os clientes em GOOGLE_ADS_CUSTOMER_ID_*
    """
    clients = list_clients()

    def _norm(name: str) -> str:
        return name.strip().upper().replace('-', '_').replace(' ', '_')

    # 1 + 2: nome explicito
    chosen = requested or os.environ.get('REPORT_CLIENT')
    if chosen:
        key = _norm(chosen)
        if key in clients:
            return key, clients[key]
        # fallback: tenta como prefixo unico
        matches = [k for k in clients if k.startswith(key)]
        if len(matches) == 1:
            return matches[0], clients[matches[0]]
        if matches:
            raise RuntimeError(
                f"Cliente '{chosen}' e ambiguo. Candidatos: {', '.join(sorted(matches))}"
            )
        raise RuntimeError(
            f"Cliente '{chosen}' nao configurado. "
            f"Disponiveis: {', '.join(sorted(clients)) or '(nenhum)'}"
        )

    # 3: legado
    legacy = os.environ.get('GOOGLE_ADS_CUSTOMER_ID')
    if legacy:
        return '', legacy.replace('-', '').strip()

    # 4: prompt
    if not clients:
        raise RuntimeError(
            "Nenhum cliente configurado. Defina GOOGLE_ADS_CUSTOMER_ID_<NOME> "
            "no .env ou passe --client <NOME>."
        )

    items = sorted(clients.items())
    print("\nClientes disponiveis:")
    for i, (nome, cid) in enumerate(items, 1):
        print(f"  {i:2d}. {nome:<24} ({cid})")
    while True:
        try:
            resp = input("\nEscolha o cliente (numero ou nome): ").strip()
        except (EOFError, KeyboardInterrupt):
            raise RuntimeError("Selecao de cliente cancelada.")
        if not resp:
            continue
        if resp.isdigit():
            idx = int(resp) - 1
            if 0 <= idx < len(items):
                return items[idx]
        key = _norm(resp)
        if key in clients:
            return key, clients[key]
        print(f"  -> opcao invalida: {resp!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Loader principal
# ─────────────────────────────────────────────────────────────────────────────

def load_report_data(client_name: str | None = None) -> ReportData:
    """
    Busca os dados na Google Ads API e devolve um ReportData equivalente ao
    que o loader de CSV produz.

    `client_name` (opcional) seleciona qual cliente usar - normalmente vem do
    flag --client da CLI. Se nao passado, usa REPORT_CLIENT, ou cai no prompt
    interativo. Veja `resolve_client()` pra detalhes.
    """
    if not _HAS_SDK:
        raise RuntimeError(
            "Pacote google-ads nao instalado. Rode `pip install -r requirements.txt`."
        )

    selected_name, customer_id = resolve_client(client_name)
    if selected_name:
        print(f"[fonte] cliente: {selected_name} ({customer_id})")
    else:
        print(f"[fonte] cliente: {customer_id}")

    client = _load_client()
    start, end = _resolve_period()
    start_str = start.strftime('%Y-%m-%d')
    end_str = end.strftime('%Y-%m-%d')

    data = ReportData(
        period_start=start,
        period_end=end,
        period_text=f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}",
        client_name=selected_name,
    )

    ga_service = client.get_service("GoogleAdsService")
    search = lambda q: ga_service.search(customer_id=customer_id, query=q)

    # ── Palavras-chave ──────────────────────────────────────────────────────
    kw_query = f"""
        SELECT
          ad_group_criterion.keyword.text,
          ad_group_criterion.keyword.match_type,
          metrics.impressions,
          metrics.clicks,
          metrics.ctr,
          metrics.average_cpc,
          metrics.cost_micros,
          metrics.conversions,
          metrics.cost_per_conversion,
          metrics.conversions_from_interactions_rate
        FROM keyword_view
        WHERE segments.date BETWEEN '{start_str}' AND '{end_str}'
    """
    for row in search(kw_query):
        m = row.metrics
        kw = row.ad_group_criterion.keyword
        mt_name = kw.match_type.name
        data.keywords.append(Keyword(
            keyword       = _format_kw(kw.text, mt_name),
            match_type    = _MATCH_TYPE_MAP.get(mt_name, mt_name),
            clicks        = int(m.clicks),
            impressions   = int(m.impressions),
            ctr_pct       = float(m.ctr) * 100,
            avg_cpc       = float(m.average_cpc) / 1_000_000,
            cost          = int(m.cost_micros) / 1_000_000,
            conversions   = float(m.conversions),
            cost_per_conv = float(m.cost_per_conversion) / 1_000_000,
            conv_rate_pct = float(m.conversions_from_interactions_rate) * 100,
        ))

    # ── Grupo de anuncios "principal" (maior numero de impressoes) ──────────
    ag_query = f"""
        SELECT
          ad_group.name,
          campaign.name,
          metrics.impressions
        FROM ad_group
        WHERE segments.date BETWEEN '{start_str}' AND '{end_str}'
          AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
        LIMIT 1
    """
    for row in search(ag_query):
        data.ad_group = row.ad_group.name
        data.campaign = row.campaign.name
        break  # so o primeiro

    # ── Serie temporal diaria ───────────────────────────────────────────────
    ts_query = f"""
        SELECT
          segments.date,
          metrics.impressions
        FROM customer
        WHERE segments.date BETWEEN '{start_str}' AND '{end_str}'
        ORDER BY segments.date
    """
    for row in search(ts_query):
        d_obj = date.fromisoformat(row.segments.date)
        label = d_obj.strftime('%d/%m')
        data.daily_impressions.append((label, int(row.metrics.impressions)))

    # ── Totais ──────────────────────────────────────────────────────────────
    for k in data.keywords:
        data.totals.impressions += k.impressions
        data.totals.clicks      += k.clicks
        data.totals.cost        += k.cost
        data.totals.conversions += k.conversions

    return data
