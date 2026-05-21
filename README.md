# googleAdsReportNishida

Gerador automatico de relatorio Google Ads (Nishida Publicidade).
Suporta duas fontes de dados: **Google Ads API** (preferida, automatica)
ou **CSVs exportados** do painel (fallback).

## Como usar

### 1. Instalar dependencias (uma vez)
```powershell
pip install -r requirements.txt
```

### 2. Escolher a fonte de dados

**Opcao A — Google Ads API (recomendado):** o script puxa os dados ao vivo,
sem precisar exportar nada. Configure as variaveis abaixo (PowerShell):

```powershell
setx GOOGLE_ADS_DEVELOPER_TOKEN     "seu-developer-token"
setx GOOGLE_ADS_CLIENT_ID           "xxx.apps.googleusercontent.com"
setx GOOGLE_ADS_CLIENT_SECRET       "xxx"
setx GOOGLE_ADS_REFRESH_TOKEN       "1//xxx"
setx GOOGLE_ADS_LOGIN_CUSTOMER_ID   "1234567890"   # opcional - apenas se usar conta MCC
setx GOOGLE_ADS_CUSTOMER_ID         "9876543210"   # conta cliente a ser consultada (sem tracos)
```
Reabra o terminal para as variaveis ficarem ativas.

Alternativa: criar um arquivo `google-ads.yaml` no diretorio do projeto ou em `~/`:
```yaml
developer_token: seu-developer-token
client_id: xxx.apps.googleusercontent.com
client_secret: xxx
refresh_token: 1//xxx
login_customer_id: 1234567890   # opcional
use_proto_plus: True
```
(Nesse caso ainda e preciso ter `GOOGLE_ADS_CUSTOMER_ID` no ambiente.)

Por padrao o periodo consultado e o **mes calendario anterior**. Para override:
```powershell
$env:REPORT_START = "2026-04-01"
$env:REPORT_END   = "2026-04-30"
```

**Opcao B — CSVs exportados:** util pra rodar offline ou pra testes. Exporte do
Google Ads e coloque em `csvs/`:
- `Relatório de palavras-chave da rede de pesquisa.csv`
- `Relatório do grupo de anúncios.csv`
- `Gráfico_de_série_temporal(YYYY.MM.DD-YYYY.MM.DD).csv`

Se as credenciais da API nao estiverem definidas, esta e a fonte automatica.
Pra forcar manualmente: `$env:REPORT_SOURCE = "csv"` (ou `"api"`).

### 3. (Opcional) Habilitar analises por IA (Claude)

```powershell
setx ANTHROPIC_API_KEY "sk-ant-..."
```
Sem a chave, o relatorio usa textos parametrizados padrao. Com a chave, os
textos de "Resumo do Periodo", "Analise das palavras-chave" e "Resumo Geral"
sao gerados pelo Claude Opus 4.7 a partir dos dados reais.

**Personalize o tom e estilo** editando [`instrucoes_ia.md`](instrucoes_ia.md) —
controla persona, publico, formato e conteudo. Nao precisa mexer no codigo.

### 4. Rodar
```powershell
python gerar_relatorio.py
```
O PDF e gerado em `output/Relatorio_GoogleAds_<periodo>.pdf`.

## Estrutura

- `gerar_relatorio.py` — script principal, monta o PDF
- `dados.py` — dataclasses compartilhadas (Keyword, AdGroup, Totals, ReportData)
- `fonte_google_ads.py` — carrega dados da API do Google Ads
- `ia_analises.py` — gera textos por IA via Claude API
- `instrucoes_ia.md` — instrucoes editaveis para a IA
- `csvs/` — CSVs de entrada (modo fallback)
- `assets/` — logos do cabecalho (`logo_nishida.png`, `logo_cliente.png`)
- `output/` — destino dos PDFs gerados

## Variaveis de ambiente — resumo

| Variavel | Obrigatoria? | Descricao |
|---|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN`     | API | Developer token do Google Ads |
| `GOOGLE_ADS_CLIENT_ID`           | API | OAuth client id |
| `GOOGLE_ADS_CLIENT_SECRET`       | API | OAuth client secret |
| `GOOGLE_ADS_REFRESH_TOKEN`       | API | Refresh token OAuth |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID`   | API (opcional) | Conta gerenciador / MCC |
| `GOOGLE_ADS_CUSTOMER_ID`         | API | Conta cliente (sem tracos) |
| `REPORT_START` / `REPORT_END`    | nao | Override do periodo (YYYY-MM-DD) |
| `REPORT_SOURCE`                  | nao | `"api"` ou `"csv"` pra forcar fonte |
| `ANTHROPIC_API_KEY`              | nao | Habilita textos gerados por IA |

## Observacoes

- O script identifica automaticamente o periodo, a campanha e o grupo de anuncios
  com maior numero de impressoes.
- Os textos parametrizados (sem IA) se adaptam ao desempenho real: se nao houver
  conversoes, o relatorio sinaliza a necessidade de revisar o rastreamento.
- A avaliacao "Acima/Dentro/Abaixo da media" usa benchmarks do varejo local
  (CTR 3 a 5%, CPC R$ 0,50 a R$ 2,00, taxa de conversao 2 a 4%, custo/conv R$ 10 a R$ 30).
