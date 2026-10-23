# ans

Pesquisa e validação de dados abertos da ANS para um scorecard de operadoras de planos de saúde.
Hoje é só pesquisa: não há pacote, site nem feed. O resultado está em `pesquisa/VALIDACAO.md`.

## Regras

- Commit por caminho (`git add` com caminhos explícitos), sem perguntar, um assunto por commit; nunca push.
- Nenhuma dependência nem pacote sem plano: scripts só com a biblioteca padrão do Python (DuckDB e httpx
  ficam para quando houver produto).
- Downloads vão para `pesquisa/downloads/AAAA-MM-DD/` (fora do git), com os cabeçalhos HTTP em
  `headers/`. Scripts ficam em `pesquisa/scripts/`, nunca na pasta de downloads, e leem os arquivos
  com `python3 -I`, recebendo o caminho como argumento.
- `curl` para o FTP (`dadosabertos.ans.gov.br`, sem `robots.txt`) e para `www.gov.br/ans` (o
  `robots.txt` não barra `/ans`; responde 200 ao `curl`, medido em 22/10/2026).
- Respeitar `robots.txt`: `www.ans.gov.br` e `www.in.gov.br` (DOU) são `Disallow: /`. As consultas
  `index.php?option=…`, `component/legislacao` (textos de RO e RN) e a busca do DOU ficam fora de
  qualquer automação; anotar o link, não raspar.
- LGPD: nenhuma linha da NIP (`pda-013`) entra no repo; só agregados por operadora, e nesta etapa
  nem isso.
- Nenhum arquivo acima de 100 MB no git (o GitHub recusa).

## Estrutura

- `pesquisa/snapshots/AAAA-MM-DD/`: cópias do que a ANS sobrescreve (CADOP diário, IGR e outros
  arquivos reprocessados, PDFs trimestrais da RN 623), só o que mudou desde o snapshot anterior, com
  `SHA256SUMS` e `FONTES.tsv`. `pesquisa/snapshots/ESTADO.tsv` guarda o `Last-Modified` e o sha256 da
  última versão de cada arquivo; gerar com `bash pesquisa/scripts/snapshot.sh`.
- `pesquisa/fixtures/`: cabeçalho + 50 registros de cada CSV (`*_head.csv`), linhas de casos
  estranhos (`*_casos.csv`), `headers_*.txt` e `manifest.json`; tudo byte a byte, `-text` no
  `.gitattributes`. Receita do `CONTRIBUTING.md` do repo `anvisa`. Regerar com
  `python3 -I pesquisa/scripts/fixtures.py pesquisa/downloads/2026-10-22 pesquisa/downloads/2026-10-23 pesquisa/fixtures`
  (cada arquivo vem da última pasta que o tenha).
- `pesquisa/scripts/`: `perfil.py` (formato de cada CSV), `validar.py` (perguntas da validação),
  `rn623.py` (reconstrução das listas RN 623), `pda055.py` (reajuste de agrupamento),
  `cadop_diff.py` (diff de dois snapshots do CADOP), `snapshot.sh` (snapshot incremental, só curl e
  coreutils).
