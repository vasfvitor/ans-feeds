# ANS, scorecard de operadoras: validação (etapa 0), 22/10/2026

O que está aqui foi medido nesta máquina em 22/10/2026, sobre arquivos baixados no mesmo dia, e não
repete a pesquisa preliminar. Scripts em `pesquisa/scripts/` (só biblioteca
padrão, rodados com `python3 -I`); downloads em `pesquisa/downloads/2026-10-22/` (fora do git). Os cinco
arquivos do snapshot do FTP batem byte a byte com o FTP no fim da tarde (`cmp` e `SHA256SUMS`).

## Resumo

- **O que funciona:** a chave casa. Depois de completar o registro com zeros à esquerda até 6 dígitos,
  100% dos registros de IGR, TR, IDSS, prudencial, garantia, ressarcimento, HC e penalidades existem no
  CADOP (ativas ∪ canceladas). Na direção técnica, só `X00002` fica de fora.
- **IGR por 100 mil ✔.** Em todas as 70.474 linhas de 2019 a 2026, `QTD_RECLAMACOES / QTD_BENEFICIARIOS ×
  100.000` dá o `IGR` exato com 2 casas. Em 2015–2018 o arquivo já está em 100 mil, mas com 1 ou 2 casas
  (1,4% das linhas não fecham).
- **As listas RN 623 se reconstroem pelo CSV.** Da Excelência 2T2026, 426 das 430 operadoras saem só da
  regra do IGR (meta 2,4 MH / 0,6 OD, ou até 3 / 2 NIPs no trimestre), com 2 falsos positivos. Com a meta
  de 60,9 citada pela Mattos Filho seriam 366 falsos positivos. A meta é 2,4/0,6.
- **O `pda-023` é série, não snapshot.** São 117 competências, de 2015-01 a 2026-09, faltando
  2019-05 → 2021-04 (24 meses), e a ANS reprocessa tudo a cada mês. Os números antigos mudam: na lista
  de Redução, a NIP do trimestre bate em 14 a 16 de 20 operadoras, e o IGR com 2 casas em só 2 a 8 de 20.
- **Três conjuntos estão parados apesar do `Last-Modified` recente.** A TR termina em **2019-10**. A
  garantia vai até o 4T2024, sem o 2T e o 3T de 2024. As penalidades têm `NR_COMPETENCIA_CARGA = 202503`
  em todas as linhas (última decisão em 31/03/2025).
- **Encoding:** 8 arquivos são UTF-8, 2 são ASCII e só as penalidades vêm em Latin-1. O "Latin-1" da
  pesquisa preliminar não vale para o FTP de hoje.
- **Fora do FTP:** o `gov.br/ans` responde 200 ao `curl` (o 403 não se repetiu). O `robots.txt` de
  `www.ans.gov.br` e o de `www.in.gov.br` (DOU) são `Disallow: /`. Direção fiscal e liquidação seguem
  sem fonte automatizável.

## Conjuntos

Base `https://dadosabertos.ans.gov.br/FTP/PDA/`, sem `robots.txt` (404). Todos usam `;` como
separador, sem quebra de linha dentro de campo (um registro por linha) e decimal com vírgula. Os campos
de texto vêm entre aspas; os números, sem aspas.

### CADOP ativas: `operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv`

`Last-Modified: Thu, 22 Oct 2026 10:00:07 GMT`; 346.860 bytes; UTF-8 sem BOM; LF; 20 colunas;
1.106 registros, nenhuma linha duplicada. `REGISTRO_OPERADORA` tem sempre 6 dígitos com zero à esquerda,
um por linha. O CNPJ tem 14 dígitos sem máscara, todos distintos. `DATA_REGISTRO_ANS` é ISO, de
1998-12-16 a 2026-10-19. Há 8 modalidades, entre elas 182 administradoras de benefícios.
`REGIAO_DE_COMERCIALIZACAO` vem vazia em 48 linhas.

### CADOP canceladas: `operadoras_de_plano_de_saude_canceladas/Relatorio_cadop_canceladas.csv`

`Last-Modified: Thu, 22 Oct 2026 10:00:07 GMT`; 1.036.861 bytes; UTF-8; LF; 22 colunas; 3.078
registros, um por registro ANS e nenhum também nas ativas. Os CNPJs distintos são 3.038: 40 CNPJs
aparecem com 2 registros. `DATA_DESCREDENCIAMENTO` é ISO, de 1999-09-20 a 2026-10-09. O CEP vem com
espaços à direita em pelo menos 6 linhas. `MOTIVO_DO_DESCREDENCIAMENTO` tem 21 valores:

| n | motivo | n | motivo |
|---:|---|---:|---|
| 1.524 | Pedido de cancelamento | 54 | Descumprimento de disposição legal |
| 306 | Descumprimento da RN n.º 100/2005 | 37 | Empresa operava com Sistema de Desconto |
| 271 | Liquidação Extrajudicial | 28 | Adequação à Lei no. 10.185/2001 |
| 246 | Deliberação de Diretoria Colegiada | 21 | Ausência de operação - Deliberação de Diretoria Colegiada |
| 192 | Alternat. à Liquidação - Deliberação de Diretoria Colegiada | 12 | Decretação de Falência por outros órgãos |
| 160 | Descumprimento da Circular SUSEP no. 77/1999 | 10 | Pedido de Cancelamento pós cisão e incorp. operação de plano |
| 116 | Por incorporação | 8 | INEXISTÊNCIA DE PRODUTO ATIVO POR MAIS DE 180 DIAS |
| 67 | Ausência de operação | 7 | AUSÊNCIA DE SOLICITAÇÃO DE REGISTRO DE PRODUTO |

Com 6 ou menos: pessoa jurídica de direito público (6), filial (5), baixa no CNPJ (4), RDC 77/2001 (3),
RN 543/2022 (1). Cancelamentos por ano: 59 (2019), 73, 62, 56, 45, 53, 38 e 34 (2026 até 09/10).

### IGR versão 2023: `IGR/IGR_versao_2023/pda-023-igr.csv`

`Last-Modified: Sat, 10 Oct 2026 11:00:10 GMT`; 17.422.407 bytes; UTF-8; LF; 10 colunas; 129.188
linhas, nenhuma duplicada.

- `REGISTRO_OPERADORA`: 6 dígitos com zero, entre aspas; 1.416 registros (894 ativos, 522 cancelados).
  Nenhuma administradora de benefícios, o que bate com a Ficha.
- `COMPETENCIA` e `COMPETENCIA_BENEFICIARIO` no formato `AAAA-MM`. As duas são iguais, salvo em 2026-09,
  que usa os beneficiários de 2026-08 (a Ficha manda repetir a competência anterior quando o SIB atrasa).
- Faltam as 24 competências de 2019-05 a 2021-04. Linhas por competência: 1.338 (2015-01), 1.067
  (2021-05), 969 (2026-09).
- `DT_ATUALIZACAO` vem vazio nas competências até 2019-04 (63.266 linhas) e com `2026-10-07` no resto.
- Há 19 chaves (registro, cobertura, competência) repetidas, todas em 2019-04: a mesma linha com a razão
  social antiga e a nova (por exemplo, `321338` AMERON com e sem "EM LIQUIDAÇÃO EXTRAJUDICIAL").
- O arquivo traz também os meses sem reclamação: 76.919 linhas com `QTD_RECLAMACOES = 0`.
  `QTD_BENEFICIARIOS` nunca é 0.
- `COBERTURA`: "Assistência médica" (85.819) / "Exclusivamente odontológica" (43.369). `PORTE_OPERADORA`:
  Pequeno, Médio e Grande.

Dicionário `Dicionario_IGR_versao_2023.ods` (2023-10-11); Ficha `Ficha_Nota_Tecnica_-_IGR.pdf`
(146.240 bytes, 2024-04-16), lida.

### Taxa de Resolutividade: `taxa_de_resolutividade/pda-048-taxa_de_resolutividade.csv`

`Last-Modified: Sat, 10 Oct 2026 11:00:06 GMT`; 6.784.117 bytes; UTF-8; LF; 8 colunas; 63.366 linhas.

- `CD_REGISTRO_ANS` tem 6 dígitos; são 1.210 registros.
- **`CD_COMPETENCIA` vai de 2015-01 a 2019-10** (58 meses, sem buraco), mas `DT_ATUALIZACAO` traz
  `2026-10-07` em todas as linhas. A pesquisa preliminar leu "desde 2019-10" porque o arquivo está em ordem
  decrescente.
- `TP_NATUREZA` tem 3 valores, não 2: Geral (26.062), Assistencial (22.340), Não Assistencial (14.964).
- `VL_TR = NR_NUMERADOR / NR_DENOMINADOR × 100` bate em 100% das linhas.

O arquivo serve como histórico, mas não como indicador atual.

### IDSS histórico: `historico_idss-020/pda-020-historico-idss-2016_2025.csv`

`Last-Modified: Tue, 23 Jun 2026 12:52:35 GMT`; 793.151 bytes; UTF-8; **CRLF**; tudo entre aspas,
inclusive o cabeçalho e os números; 54 colunas; 1.885 linhas, uma por registro (848 ativos, 1.037
cancelados). O CNPJ vem com máscara.

- São 50 colunas de índice: 5 dimensões (IDSS, IDQS, IDGA, IDSM, IDGR) × 10 pares
  `ID??_<ano de divulgação>_<ano-base>`. Os valores têm precisão variável (`0,5222`, `0,59`, `1`).
- "ND" ocupa 50.526 das 94.250 células. Só no IDSS são 910 linhas ND em 2016_2015 e 1.082 em 2025_2024.
- 727 operadoras são ND em tudo: 717 canceladas e 10 ativas (entre elas Unimed-Rio `393321`, Unimed
  Taubaté `363286`, Unimed Manaus `311961`, Unimed Petrópolis `323993`).

### Direção técnica: `regimes_especiais_direcao_tecnica/pda-040-regimes_especiais_direcao_tecnica.csv`

`Last-Modified: Mon, 19 Jan 2026 18:54:45 GMT`; 9.770 bytes; UTF-8; **CRLF**; números sem aspas; 6
colunas; 118 linhas (RO única por linha).

- 77 registros, dos quais 75 com 6 dígitos. Os outros dois: `X00002` (RO 156, 2003, Montepio da Família
  Pernambucana) e `303623 ` com espaço à direita (RO 171, 2003).
- `DATA_PUBLICACAO` é ISO. A última RO é a 3077, de **2025-12-11**: o 19/01/2026 da pesquisa preliminar é a data do
  arquivo, não de uma RO.
- Por ano: 4, 6, 6, 3, 7, 6 e 4 de 2018 a 2024, e **22 em 2025**.

### Classificação prudencial: `classificacao_prudencial-056/pda-056-classificacao_prudencial.csv`

`Last-Modified: Thu, 30 Jul 2026 10:00:11 GMT`; 333.402 bytes; ASCII; LF; 3 colunas; 12.346 linhas;
1.226 registros (1.101 ativos).

- `DT_TRIMESTRE_REFERENCIA` é ISO, com 11 trimestres de 2024-03-31 a 2026-09-30. Um arquivo de 30/07 já
  traz o trimestre que fecha em 30/09: a classificação vale *para* o trimestre, não o descreve.
- Distribuição: S1 263, S2 1.656, S3 5.751, S4 4.676 (cerca de 1.120 por trimestre).

### Garantia de atendimento: `monitoramento_garantia_atendimento/monit_garantia_atendimento.csv`

`Last-Modified: Sat, 10 Oct 2026 11:00:03 GMT`; 3.666.924 bytes; UTF-8; LF; 6 colunas; 33.025 linhas.

- **`REGISTRO_OPERADORA` é inteiro sem aspas** e perde o zero à esquerda (`27`, `477`, `515`). Isso
  acontece em 9 registros e 248 linhas.
- `COMPETENCIA` vem como `"4º Trim./2015"`, mais `DT_INICIO`/`DT_FIM` em ISO.
- **São 35 trimestres, de 4T2015 a 4T2024, sem o 2T e o 3T de 2024.**
- `POSICAO`: FAIXA 0 (27.146), 1 (2.916), 2 (844), 3 (2.119).

### Ressarcimento ao SUS, índice de efetivo pagamento: `ressarcimento_ao_SUS_indice_efetivo_pagamento/202609_Indice_de_Efetivo_Pagamento.csv`

`Last-Modified: Mon, 05 Oct 2026 17:56:46 GMT`; 247.895 bytes; UTF-8; LF; 13 colunas; 1.683 linhas, uma
por operadora. Há um arquivo por mês (`AAAAMM_`).

- `CODIGO_OPERADORA` tem 6 dígitos, salvo 2 linhas com 5.
- `COMPETENCIA` vem como `AAAA-MM`.
- Os valores usam vírgula decimal; os índices vêm com `%` (`"91,31%"`). `INDICE_ADIMPLENCIA_5ANOS` está
  vazio em 755 linhas.
- `SITUACAO_OPERADORA`: 1 (638) e 2 (1.045). As contagens são as mesmas dos registros em CADOP
  ativas e canceladas, logo 1 = ativa e 2 = cancelada (não conferido linha a linha).

### Ressarcimento ao SUS, HC: `hc_ressarcimento_sus/HC_2026.csv`

`Last-Modified: Tue, 06 Oct 2026 16:00:04 GMT`; 640.204 bytes; ASCII; LF; 3 colunas; 27.181 linhas.
Há um arquivo por ano, regravado a cada mês.

- **`CD_OPERADORA` mistura formatos no mesmo arquivo:** 6 dígitos em 25.759 linhas e 5 dígitos em 1.422
  (158 registros).
- `COMPETENCIA` vem como `AAAAMM` (202601 a 202609); `PORCENTAGEM_HC` usa vírgula decimal.
- São 3.031 registros, dos quais 2.154 cancelados.

### Penalidades: `penalidades_aplicadas_a_operadoras/penalidades_aplicadas_a_operadoras.csv`

`Last-Modified: Mon, 05 Oct 2026 12:01:33 GMT`; 41.160.878 bytes (7.514.726 em gzip -9); **Latin-1**,
sem bytes 0x80–0x9F; LF; cabeçalho sem aspas; 42 colunas; 111.928 linhas, cerca de 368 bytes cada.
Detalhes na pergunta 6.

### Fora do FTP

- **Listas RN 623**, em `gov.br/ans/…/lista-excelencia-e-reducao-das-reclamacoes-das-operadoras`
  (resposta 200 ao `curl`). Os PDFs do 2T2026:

  | lista | bytes | páginas | operadoras |
  |---|---:|---:|---:|
  | MH Excelência | 496.395 | 4 | 221 |
  | OD Excelência | 493.653 | 4 | 209 |
  | MH Redução | 450.309 | 1 | 20 |
  | OD Redução | 425.889 | 1 | 1 |

  O nome dos arquivos muda de trimestre para trimestre (`Lista_OPS_MH_Excelncia__2T2026__GCOMS.pdf`,
  `…Excelencia__1T2026…`, `Lista_de_Excelncia_no_relacionamento…4T2025.pdf`, e o 3T2025 em outra pasta).
  O texto do PDF sai embaralhado com `pdftotext -layout`; lido por coordenadas (`-bbox`, em
  `scripts/rn623.py`), sai inteiro. A página tem 5 links de Power BI e nenhum CSV.
- **Portabilidade especial** (`…/operadoras-em-fase-de-portabilidade-especial-e-portabilidade-extraordinaria`):
  224.698 bytes, "Atualizado em 24/02/2026". Três tabelas: 14 vigentes (de 12/03/2025 a 24/02/2026), 105
  encerradas (2018–2023) e 18 de portabilidade extraordinária. Colunas: data no DOU, operadora, nº da RO
  e link. Não há registro ANS nem prazo.
  - A RO 3.135 (18/05/2026, noticiada) não está na página: ela está defasada.
  - O link da RO 2981 (Special Care) aponta para o PDF da Unimed Montes Claros: o erro de link se confirma.
  - Os links misturam `ans.gov.br/component/legislacao` (barrado pelo `robots.txt`), PDFs no `gov.br` e
    um `pesquisa.in.gov.br`.
- **IDSS ano-base 2024 em XLSX**: `Listagem_Completa_dos_resultados_do_IDSS__2024__v1__2026_05_07.xlsx`
  (96.213 bytes, aba única). Traz 803 operadoras, as mesmas 803 com valor em `IDSS_2025_2024` no CSV, com
  as 4.015 células iguais nas 4 casas, mais 39 linhas de subtítulo (modalidade × porte). Para as 5
  dimensões, não acrescenta nada ao `pda-020`. O detalhe por indicador está na
  `planilha_eletrnica_Dados_do_PQO…`, que não foi lida.
- **`robots.txt`**:
  - `www.ans.gov.br`: `User-agent: *` / `Disallow: /`, o host inteiro. Isso inclui
    `component/legislacao`, onde estão os textos das ROs e da RN 623, e a busca de ROs.
  - `www.in.gov.br`: `Disallow: /`.
  - `www.gov.br`: não barra `/ans`.

## Perguntas da validação

| # | pergunta | | resposta medida |
|---|---|---|---|
| 1 | IGR: 10 mil ou 100 mil; qual meta | ✔ | 100 mil, por aritmética e pela Ficha. A meta é 2,4 MH / 0,6 OD por trimestre, ou até 3 / 2 NIPs; a reconstrução acerta 426 de 430 operadoras. |
| 2 | Direção fiscal e liquidação | ✖ | Não há fonte automatizável: o DOU e o `ans.gov.br` são `Disallow: /`. Há só sinais indiretos (abaixo). |
| 3 | Beneficiários: basta o IGR? | ✔ | Sim para o scorecard. O SIB fica para UF e município (pergunta anotada). |
| 4 | Reajuste coletivo (RPC × PDA-055) | ✖ | Fora desta etapa (RPC são 50 MB por mês). |
| 5 | consumidor.gov.br | ✖ | Fora desta etapa (decisão de escopo). |
| 6 | Penalidades: cabeçalho | ✔ | Lido: 42 colunas, chave, período e tamanho (abaixo). O conteúdo está parado em 03/2025. |
| 7 | GitHub e Base dos Dados | ◐ | GitHub: 7 repositórios, nenhum faz scorecard. A Base dos Dados não foi buscada. |
| 8 | Power BI RN 623 e XLSX do IDSS ab 2024 | ◐ | O XLSX é igual ao CSV (✔). O Power BI não foi aberto: não se depende dele. |

### 1. IGR: escala e meta

- **Escala.** `IGR = QTD_RECLAMACOES / QTD_BENEFICIARIOS × 100.000` com arredondamento a 2 casas bate
  em 114.180 das 129.188 linhas. Por período:
  - 2019 a 2026: 70.474 de 70.474.
  - 2015 a 2018: 43.706 batem com 2 casas, 14.174 com 1 casa e 834 não batem (o valor publicado fica a
    alguns centésimos; por exemplo, `303267` em 2018-05: 2 / 97.402 → 2,05, publicado 2,00).

  Com base 10.000 só batem as 76.919 linhas com zero reclamação, que batem com qualquer base. **Não há
  linha em 10 mil no arquivo.**
- **As 10 maiores de assistência médica em 2026-09**, contas exatas:

  | registro | operadora | NIP | beneficiários | IGR |
  |---|---|---:|---:|---:|
  | 368253 | Hapvida | 2.187 | 4.321.673 | 50,61 |
  | 005711 | Bradesco Saúde | 2.813 | 3.391.379 | 82,95 |
  | 359017 | NotreDame Intermédica | 2.398 | 3.228.400 | 74,28 |
  | 326305 | Amil | 2.097 | 3.206.620 | 65,40 |
  | 006246 | Sul América Cia. de Seguro Saúde | 2.501 | 2.438.807 | 102,55 |
  | 339679 | Unimed CNU | 1.180 | 1.699.764 | 69,42 |
  | 343889 | Unimed BH | 774 | 1.623.690 | 47,67 |
  | 000701 | Unimed Seguros | 630 | 1.022.957 | 61,59 |
  | 000582 | Porto Seguro | 605 | 877.202 | 68,97 |
  | 416428 | Sul América Paraná Clínicas | 340 | 724.184 | 46,95 |
- **A Ficha Técnica** (lida) define o IGR como a média mensal de NIPs (inativas, NP, RVE, Núcleo e em
  andamento; exclui NA) ÷ a média de beneficiários × 100.000, em qualquer período a partir de um mês
  fechado. É provisória e reprocessada retroativamente a cada mês. Não é calculada para administradoras.
- **Meta da RN 623.** O texto dos PDFs do 2T2026 diz: meta de Excelência 2,4 MH e 0,6 OD, que é a meta
  do indicador 3.3 do IDSS de 2026 (2 e 0,5) mais 20%. A meta também se cumpre com até 3 NIPs MH ou 2 OD
  no trimestre, cumulativamente para quem tem as duas coberturas. O texto da RN não foi lido (fica em
  `ans.gov.br`, barrado pelo `robots.txt`). A meta foi fixada pelo teste: reconstruí a Excelência 2T2026
  com cada meta candidata.

  | meta MH / OD | previstas | também oficiais | falsos positivos |
  |---|---:|---:|---:|
  | **2,4 / 0,6** | 428 | 426 | **2** |
  | 0 / 0 (só o atalho de NIPs) | 424 | 422 | 2 |
  | 24 / 6 | 643 | 426 | 217 |
  | 30,5 / 30,5 | 680 | 426 | 254 |
  | 60,9 / 60,9 (Mattos Filho) | 792 | 426 | 366 |

  Os valores da Mattos Filho não são os da lista oficial. A meta muda com o IDSS de cada ano: guardar o
  valor por trimestre, lido do PDF.

### Reconstrução das listas RN 623 a partir do `pda-023`

Fórmula conferida no PDF: `IGR_trim = (NIP do trimestre ÷ 3) ÷ média dos beneficiários dos 3 meses ×
100.000`. Por exemplo, Unimed Meio Oeste: 2 NIPs, 21.356 beneficiários → 3,12, na lista pelo atalho.
Comparação com os PDFs do 2T2026 (`scripts/rn623.py`):

| lista | linhas | NIP igual | IGR igual (±0,01) | média de beneficiários |
|---|---:|---:|---:|---|
| Excelência MH, bloco MH | 212 | 205 | 185 | desvio mediano 0,036%, p90 0,93% |
| Excelência MH, bloco OD | 11 | 11 | 11 | |
| Excelência OD | 208 | 204 | 201 | desvio mediano 0,022%, p90 0,43% |
| Redução MH, 4T25 / 1T26 / 2T26 | 20 × 3 | 16 / 16 / 14 | 2 / 6 / 8 | |
| Redução MH, bloco OD | 4 × 3 | 12/12 | 12/12 | |
| Redução OD | 1 × 3 | 3/3 | 3/3 | |

- Das 430 operadoras oficiais da Excelência, **4 não têm linha no CSV no 2T2026**: `324892`, `340162`,
  `359726` e `418447`. As últimas competências delas vão de 2025-12 a 2026-03, e três foram canceladas
  em setembro de 2026. A ANS as lista com 0 NIP; o CSV só traz operadora-mês com beneficiários.
- Os 2 falsos positivos: `418501`, com 3 NIPs MH no CSV de hoje (provavelmente 4 quando a lista saiu), e
  `424897`, com 2 beneficiários e registro recente.
- **O que isso responde:** como o CSV traz a série inteira, a reconstrução funciona **para trás** e não
  só daqui para a frente. Mas os números ficam *aproximados*, porque o reprocessamento mensal muda NIPs
  (classificação) e beneficiários (SIB). Para reproduzir exatamente uma lista publicada, é preciso o
  snapshot do `pda-023` do mês da publicação. É por isso que o IGR entra no snapshot mensal.

### 2. Direção fiscal e liquidação

- **DOU.** `www.in.gov.br/robots.txt` é `Disallow: /`. Uma única requisição à busca (`/consulta/-/buscar/dou?q=…`)
  respondeu 200 com 148.676 bytes de HTML; o conteúdo não foi raspado. O INLABS (`inlabs.in.gov.br`,
  XML do DOU, exige cadastro) respondeu 301 na raiz e 404 no `robots.txt`, com a página "Sistema em
  Manutenção". A rota sancionada seria o INLABS com cadastro, não verificada.
- **ANS.** A consulta de regimes (`index.php?option=com_regimeespecial`) e os textos de RO
  (`component/legislacao`) ficam em `www.ans.gov.br`, que é `Disallow: /`.
- **Sinais indiretos que existem no FTP:**
  - CADOP canceladas com motivo "Liquidação Extrajudicial": 271 no total, 15 desde 2024, a última em
    2026-09-22 (`422134`). A data registrada é a do cancelamento, não a da decretação.
  - Sufixo na razão social: 4 operadoras ativas e também presentes no IGR de 2026-09. Duas estão "EM
    LIQUIDAÇÃO EXTRAJUDICIAL" (`412635`, `419516`) e duas "EM RECUPERAÇÃO JUDICIAL" (`313971`, `324213`).
  - IDSS todo "ND" em 10 operadoras ativas (art. 23 da RN 505: não divulgado para quem está em regime).
- **Resposta:** lançar o feed com técnica + portabilidade + cancelamento, e marcar fiscal e liquidação
  como "fonte: DOU, manual" até haver INLABS.

### 3. Beneficiários

`QTD_BENEFICIARIOS` do IGR basta para o scorecard. Ele vem por operadora × cobertura × mês e soma
53.164.516 beneficiários em assistência médica e 37.311.529 em odontologia em 2026-09 (base de
2026-08), a ordem de grandeza do mercado. Cobre 886 das 924 operadoras ativas que não são
administradoras.

Das 40 que faltam em 2026-09, 30 nunca aparecem no IGR. Têm registro recente (de 2022-12-26 a
2026-10-19) ou nenhum beneficiário; administradoras não têm beneficiário no SIB. O SIB e o PDA-024 só
seriam necessários para quebrar por UF ou município: **pergunta anotada, não respondida** (ZIPs de até
3 GB, fora desta etapa).

### 6. Penalidades

- **Chave:** `REGISTRO_OPERADORA` (6 dígitos entre aspas; 5 dígitos em 13 linhas; vazio em 433) e CNPJ
  com máscara (vazio em 98). São 2.304 registros, todos no CADOP depois de completar os zeros.
- **Uma linha por demanda:** `NR_DEMANDA`, `NR_PROCESSO` (44 processos repetidos), `TIPO_PROCESSO`
  (Consumidor 100.765, Representação 9.029, Institucional 1.840, Olho Vivo 294).
- **Datas** em `dd/mm/aaaa`; valores em reais inteiros (`VL_MULTA_FIXA_1A = 47520`).
- **`NR_GRU` começa com TAB** em todas as linhas, um truque para o Excel não converter o número.
- **Período:** `DT_DECISAO_1A` de 2000-03-15 a 2025-03-31. A data mais recente em qualquer `DT_*` é
  2026-08-31, um vencimento de GRU. `NR_COMPETENCIA_CARGA` é `202503` em todas as linhas: **a carga
  parou em março de 2025** e o arquivo é regravado todo mês sem conteúdo novo.
- **Volume:** decisões de 1ª instância por ano foram 7.483 (2021), 5.924, 7.257 e 7.708 (2024), cerca de
  640 linhas e 235 KB por mês. O arquivo, porém, sai inteiro: 41,2 MB, ou 7,5 MB em gzip.

### 7. GitHub

Quatro buscas na API pública de repositórios (sem autenticação; o `gh` não tem credencial no sandbox)
devolveram 7 repositórios: análises de TISS e NIP, cargas SQL, uma EDA. Nenhum cruza indicadores por
operadora nem publica scorecard. Com o healthbR (R), o terreno continua livre. A Base dos
Dados não foi buscada, e a busca de código exige token.

### Junção pelo registro

Registros de cada conjunto que existem no CADOP (ativas ∪ canceladas), depois de completar com zeros até
6 dígitos (`scripts/validar.py`):

| conjunto | registros | sem zero à esquerda | ativas | canceladas | casam | sem completar os zeros |
|---|---:|---:|---:|---:|---:|---:|
| IGR | 1.416 | 0 | 894 | 522 | 100% | 100% |
| TR | 1.210 | 0 | 725 | 485 | 100% | 100% |
| IDSS 2016_2025 | 1.885 | 0 | 848 | 1.037 | 100% | 100% |
| prudencial | 1.226 | 0 | 1.101 | 125 | 100% | 100% |
| garantia | 1.242 | 9 | 867 | 375 | 100% | 1.233 |
| ressarcimento 202609 | 1.683 | 2 | 638 | 1.045 | 100% | 1.681 |
| HC 2026 | 3.031 | 158 | 877 | 2.154 | 100% | 2.873 |
| penalidades | 2.304 | 12 | 872 | 1.432 | 100% | 2.292 |
| direção técnica | 77 | 0 | 29 | 47 | 76 de 77 | 75 |

Sobra só `X00002`. Depois de `strip()`, o `303623 ` casa.

### CADOP diff

**Pendente para 23/10/2026.** O script `scripts/cadop_diff.py` está pronto, testado com duas cópias do
dia 22 (0 entradas, 0 saídas, 0 alterações). Enquanto o diff não
sai, a própria lista de canceladas dá a série de saídas, com data e motivo. As 8 mais recentes vão de
09/09 a 09/10/2026: 4 por pedido de cancelamento, 3 por "Alternat. à Liquidação" e 1 por liquidação
extrajudicial.

### IDSS

- **Formato longo à mão** (`registro;ano_divulgação;ano_base;dimensão;valor`), conferido em 3 operadoras:

  ```
  000027;2016;2015;IDSS;ND        005711;2016;2015;IDSS;0,882     368253;2016;2015;IDSS;0,7713
  000027;2017;2016;IDSS;0,5222    005711;2019;2018;IDSS;1         368253;2022;2021;IDSS;0,8082
  000027;2018–2025;IDSS;ND        005711;2025;2024;IDSS;0,8112    368253;2025;2024;IDSS;0,7693
  ```

  Ao converter: o valor `1` vem sem casa decimal, e o ND precisa virar nulo com um motivo.
- **Sul América.** O registro com tudo ND é o `000043` (Sul América Seguro Saúde S/A), cancelado em
  **2013-05-07 "Por incorporação"**. É ausência de dado, não regra de divulgação. A Sul America Cia. de
  Seguro Saúde ativa (`006246`) tem as 50 células preenchidas. O `000477` foi incorporado em 2025-07-31 e
  só fica ND em 2025_2024.

## Correções à pesquisa preliminar

1. Encoding: UTF-8 (8 arquivos), ASCII (prudencial, HC) e Latin-1 só nas penalidades. Não é Latin-1 em
   geral.
2. O `pda-023` é a série 2015-01 → 2026-09 (117 competências, buraco de 2019-05 a 2021-04), não um
   snapshot da competência corrente.
3. A TR termina em 2019-10 (não começa); `TP_NATUREZA` tem 3 valores.
4. A garantia vai até o 4T2024, sem o 2T e o 3T de 2024, e o registro perde o zero à esquerda. O HC
   também mistura 5 e 6 dígitos.
5. As penalidades estão paradas na carga 202503 apesar do `Last-Modified` mensal.
6. Na direção técnica, a última RO é de 2025-12-11 (19/01/2026 é a data do arquivo).
7. "Sul América todo ND" é o registro `000043`, incorporado em 2013.
8. O `gov.br/ans` responde 200 ao `curl`. O `robots.txt` do `ans.gov.br` barra o host inteiro, não só
   `index.php`.
9. A meta da RN 623 é 2,4 / 0,6 (teste acima). 60,9 / 30,5 não é a meta das listas.

## Snapshots e fixtures

- `pesquisa/snapshots/2026-10-22/` (34 MB, 23 arquivos, `SHA256SUMS`):
  - do FTP: CADOP ativas e canceladas, IGR, TR, direção técnica, prudencial, garantia, HC 2026 e IDSS
    2016_2025;
  - do gov.br: as 14 listas RN 623 ainda no ar (3T2025 a 2T2026) e a página de portabilidade especial.

  O `ESTADO.tsv` e o `scripts/snapshot.sh` continuam a série.
- `pesquisa/fixtures/`: para cada um dos 11 CSVs, `*_head.csv` (cabeçalho + 50 registros, conferido com
  `cmp` contra o começo do arquivo) e `headers_*.txt` (resposta HTTP + nota). Mais `*_casos.csv` em 6
  conjuntos, com as linhas que os 50 primeiros não cobrem (registro sem zero, DT vazia, duplicata de
  2019-04, IGR com 1 casa, registro vazio, todo ND), conferidas linha a linha contra o original;
  `manifest.json`; `.gitattributes` com `-text`.

## Recomendação

**(c), os dois, nesta ordem: primeiro o snapshot, depois o feed de eventos (a), por último os dados por
operadora (b).** Só o snapshot é irreversível: o resto se reconstrói a qualquer momento a partir do FTP.

1. **Snapshot agendado, já.**

   | o quê | frequência | bruto | gzip -9 | por ano (gzip) |
   |---|---|---:|---:|---:|
   | CADOP ativas + canceladas | diário, às 07:00 | 1.383.721 bytes | 430.713 bytes | ~157 MB |
   | `pda-023` (quando `DT_ATUALIZACAO` mudar) | mensal | 17,4 MB | 2,8 MB | ~34 MB |
   | 4 PDFs RN 623 | trimestral | 1,87 MB | | 7,5 MB |
   | portabilidade + direção técnica | semanal | ~235 KB | | |

   O CADOP bruto diário no git daria ~505 MB por ano: grande demais para o repo, cujo limite recomendado
   pelo GitHub é 1 GB. Proposta: guardar no git o diff diário (KB) mais um snapshot cheio por mês em
   gzip (~430 KB, ~5 MB por ano), e o diário bruto num artefato fora do git. Se vira GitHub Action,
   decidir depois do diff de 23/10, que mostra quanto muda num dia.
2. **(a) Feed de eventos, no padrão `anvisa-feeds`.**
   - Cancelamentos com motivo: 34 a 73 por ano desde 2019, 15 por liquidação desde 2024.
   - Novos registros.
   - Direção técnica: 22 ROs em 2025.
   - Portabilidade: a página está defasada (sem a RO 3.135) e sem registro ANS, então precisa de ligação
     por nome → CADOP e de conferência dos links.
   - Fiscal e liquidação entram como "fonte: DOU, manual".

   O volume é de poucos eventos por semana; o feed cabe em KB.
3. **(b) Dados por operadora, no padrão `anvisa.dados`, com página por registro** (4.184 registros:
   1.106 ativos + 3.078 cancelados).
   - IGR mensal desde 2015, com o buraco 2019-05 → 2021-04 explícito.
   - IGR trimestral e a situação na RN 623, reconstruídos (426/430).
   - IDSS 2016–2025 em formato longo (ND com motivo).
   - Prudencial S1–S4, HC e índice de ressarcimento.
   - Cadastro e eventos do CADOP.

   TR (até 2019-10), garantia (até 4T2024, com buraco) e penalidades (até 03/2025) só entram com a data
   do último dado bem à vista, ou ficam de fora até a ANS voltar a atualizar.

   Entrada mensal: ~22 MB brutos, sem contar as penalidades. O tamanho em Parquet não foi medido (sem
   DuckDB nesta etapa). No GitHub Pages (site até 1 GB, 100 GB de banda por mês, limites flexíveis), 4.184
   páginas de alguns KB cabem com folga. O que pesa é publicar séries cheias por arquivo, não as páginas.
