# Dados por operadora (`/dados/`)

Gerados a cada build a partir dos snapshots dos dados abertos da ANS. São só fatos, com a base e a
fonte de cada número: nenhuma nota ou rótulo próprio. Datas em ISO (`AAAA-MM-DD`); número ausente é
`null`.

## `operadoras.json`

Índice para busca: uma lista com as operadoras ativas e as canceladas nos últimos 5 anos.

| campo | o que é |
|---|---|
| `registro` | registro na ANS, 6 dígitos (chave de tudo) |
| `nome`, `fantasia` | razão social e nome fantasia (este pode ser `null`) |
| `uf`, `municipio` | sede |
| `modalidade` | ex.: Medicina de Grupo, Cooperativa Médica, Odontologia de Grupo |
| `situacao` | `ativa` ou `cancelada` |
| `beneficiarios` | total no último mês do IGR (todas as coberturas), ou `null` |
| `beneficiarios_em` | o mês desse total (`AAAA-MM`), ou `null` com ele |

## `operadora/<registro>.json`

Os campos do índice, mais:

| campo | o que é |
|---|---|
| `cnpj`, `registrada_em` | do cadastro (CADOP) |
| `cancelamento` | `{data, motivo}` se cancelada, senão `null` |
| `reclamacoes` | lista, uma por cobertura (`médico-hospitalar`, `odontológica`) |
| `reclamacoes[].indice` | reclamações (NIP) por mês para cada 100 mil beneficiários no `trimestre`, pela fórmula da RN 623: (reclamações do trimestre ÷ 3) ÷ média de beneficiários × 100.000 |
| `reclamacoes[].reclamacoes`, `beneficiarios_media` | a base do índice (com poucas reclamações, o índice oscila muito) |
| `reclamacoes[].porte`, `mediana_mesmo_porte`, `operadoras_mesmo_porte` | a comparação: mediana do índice entre as operadoras do mesmo porte e cobertura, no mesmo trimestre. O porte é o da ANS (`PORTE_OPERADORA` do IGR, pelos vínculos ativos no SIB): Pequeno abaixo de 20 mil, Médio de 20 mil a 100 mil, Grande acima de 100 mil (dicionário do IGR, versão 2023) |
| `reclamacoes[].serie` | até 8 trimestres: `{trimestre, indice, reclamacoes}` |
| `meta_rn623` | a meta de reclamações da RN 623 (lista de Excelência) no `trimestre` das `reclamacoes`, pela nossa conta sobre o IGR: `atingiu` é `true` quando, em cada cobertura, o `indice` fica até a `meta` do ano (2026: 2,4 médico-hospitalar, 0,6 odontológica) ou as reclamações ficam até `ate_reclamacoes` (3 e 2). `listas` traz os PDFs oficiais desse trimestre, quando já saíram. Refazendo a lista do 2T2026 assim, 424 das 430 operadoras batem e 1 sobra; as que faltam não têm os 3 meses no IGR. `null` sem reclamações completas no trimestre ou sem a meta do ano |
| `idss` | Índice de Desempenho da Saúde Suplementar (0 a 1, maior é melhor) do último ano publicado: `valor`, `ano`, `ano_base`, as 4 `dimensoes` e a `mediana_mesma_modalidade`; com `valor` `null`, o `motivo` |
| `ressarcimento` | ressarcimento ao SUS (quando um cliente da operadora é atendido no SUS, a operadora deve pagar): `indice_pagamento` é o índice de efetivo pagamento da ANS, acumulado e nos últimos 5 anos, na `competencia`, que é (pago + parcelado) ÷ cobrado; `valor_cobrado`, `valor_pago` e `valor_parcelado` são a base, acumulada. A base não separa valor em discussão administrativa ou judicial: o que não foi pago nem parcelado pode estar contestado |
| `portabilidade_vigente` | lista de `{ro, data, link}` quando os clientes podem trocar de plano sem cumprir carência de novo |
| `eventos` | cancelamento, registro, direção técnica e portabilidade: `{tipo, id, data, titulo}`, do mais recente ao mais antigo |
| `fontes` | URL de cada conjunto de dados usado |
| `feed` | URL do feed Atom da operadora (`/operadora/<registro>.xml`): os eventos, uma entrada por trimestre de reclamações e uma por ano do IDSS; as entradas apontam para `https://saude.abelhaninja.de/plano/<registro>/` |
| `fora` | indicadores que existem mas a ANS parou de atualizar |

## `todas.json`

`{date, operadoras: [...]}`, em que `date` é o dia dos dados (o mesmo do `meta.json`) e cada item é
exatamente o conteúdo do `operadora/<registro>.json` correspondente, na ordem do índice. É para quem
precisa de tudo de uma vez; para uma operadora só, use o arquivo individual.

## `tabelas/`

Os mesmos dados em CSV, para quem redistribui (Procon, associações, imprensa): `;` entre os campos,
vírgula decimal e UTF-8 com BOM, como a ANS publica, para abrir direto numa planilha em português. Nenhuma
tabela é um ranking: a ordem é por data ou por registro.

| arquivo | uma linha por | colunas |
|---|---|---|
| `portabilidade-vigente.csv` | Resolução Operacional de portabilidade especial em vigor, da mais recente à mais antiga | `registro`, `operadora`, `uf`, `situacao`, `resolucao_operacional`, `data`, `link` |
| `fechamentos-12-meses.csv` | operadora com o registro cancelado nos 365 dias até `date`, da mais recente à mais antiga | `registro`, `operadora`, `uf`, `modalidade`, `data`, `motivo` (como a ANS escreve) |
| `ressarcimento-sus.csv` | operadora com ressarcimento ao SUS, por registro | `registro`, `operadora`, `competencia`, `valor_cobrado`, `valor_pago`, `valor_parcelado` (em reais, acumulados), `indice_pagamento`, `indice_pagamento_5anos` (em %, (pago + parcelado) ÷ cobrado) |

## O que fica de fora, e por quê

- **Classificação prudencial (S1–S4):** é um segmento por porte e perfil de risco, usado pela ANS para
  regras de capital; não é nota de saúde financeira.
- **`PORCENTAGEM_HC`** (ressarcimento): significado não verificado.
- **Taxa de resolutividade, garantia de atendimento e penalidades:** a ANS parou de atualizar (ver `fora`).
- **Contatos** do cadastro (e-mail, telefone, representante): não são publicados aqui.
