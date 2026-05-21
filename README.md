# googleAdsReportNishida

Gerador automatico de relatorio Google Ads (Nishida Publicidade) a partir dos CSVs exportados.

## Como usar

1. **Instalar dependencia** (uma vez):
   ```powershell
   pip install -r requirements.txt
   ```

2. **Exportar os CSVs do Google Ads** e colocar em `csvs/` com estes nomes:
   - `Relatório de palavras-chave da rede de pesquisa.csv`
   - `Relatório do grupo de anúncios.csv`
   - `Gráfico_de_série_temporal(YYYY.MM.DD-YYYY.MM.DD).csv`

3. **(Opcional) Habilitar analises por IA** (Claude):
   ```powershell
   $env:ANTHROPIC_API_KEY = "sk-ant-..."   # PowerShell (sessao atual)
   ```
   Para persistir: `setx ANTHROPIC_API_KEY "sk-ant-..."` e reabra o terminal.

   Sem a chave, o relatorio usa textos parametrizados padrao (deterministicos).
   Com a chave, os textos de "Resumo do Periodo", "Analise das palavras-chave" e
   "Resumo Geral" sao gerados pelo Claude Opus 4.7 a partir dos dados reais.

   **Personalize o tom e o estilo** editando [`instrucoes_ia.md`](instrucoes_ia.md) —
   o arquivo controla a persona, o publico-alvo, o formato e o que cada parte
   deve dizer. Nao precisa mexer no codigo.

4. **Rodar**:
   ```powershell
   python gerar_relatorio.py
   ```

   O PDF e gerado em `output/Relatorio_GoogleAds_<periodo>.pdf`.

## Estrutura

- `csvs/` — CSVs de entrada (relatorios exportados do Google Ads em UTF-8)
- `assets/` — logos usados no cabecalho (`logo_nishida.png`, `logo_cliente.png`)
- `output/` — destino dos PDFs gerados
- `gerar_relatorio.py` — script principal
- `ia_analises.py` — modulo de geracao de textos por IA (Claude API)
- `instrucoes_ia.md` — instrucoes editaveis para a IA (persona, tom, conteudo)

## Observacoes

- O script identifica automaticamente o periodo, a campanha e o grupo de anuncios
  com maior numero de impressoes.
- Os textos de resumo/analise se adaptam ao desempenho real: se nao houver conversoes,
  o relatorio sinaliza a necessidade de revisar o rastreamento.
- A avaliacao "Acima/Dentro/Abaixo da media" usa benchmarks do varejo local
  (CTR 3 a 5%, CPC R$ 0,50 a R$ 2,00, taxa de conversao 2 a 4%, custo/conv R$ 10 a R$ 30).
