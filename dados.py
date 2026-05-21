"""
Estruturas de dados compartilhadas entre as fontes (CSV / API) e o gerador
do PDF. Mantido propositalmente "burro" - so dataclasses + propriedades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Keyword:
    keyword: str
    match_type: str
    clicks: int
    impressions: int
    ctr_pct: float          # 6.98 significa 6,98 %
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
    client_name: str = ''     # nome do cliente (so quando a fonte e Google Ads API)
    campaign: str = ''
    ad_group: str = ''
    keywords: list[Keyword] = field(default_factory=list)
    totals: Totals = field(default_factory=Totals)
    daily_impressions: list[tuple[str, int]] = field(default_factory=list)
