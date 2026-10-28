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

## `operadora/<registro>.json`

Os campos do índice, mais:

| campo | o que é |
|---|---|
| `cnpj`, `registrada_em` | do cadastro (CADOP) |
| `cancelamento` | `{data, motivo}` se cancelada, senão `null` |
| `reclamacoes` | lista, uma por cobertura (`médico-hospitalar`, `odontológica`) |
| `reclamacoes[].indice` | reclamações (NIP) por mês para cada 100 mil beneficiários no `trimestre`, pela fórmula da RN 623: (reclamações do trimestre ÷ 3) ÷ média de beneficiários × 100.000 |
| `reclamacoes[].reclamacoes`, `beneficiarios_media` | a base do índice (com poucas reclamações, o índice oscila muito) |
| `reclamacoes[].porte`, `mediana_mesmo_porte`, `operadoras_mesmo_porte` | a comparação: mediana do índice entre as operadoras do mesmo porte (Pequeno, Médio, Grande) e cobertura, no mesmo trimestre |
| `reclamacoes[].serie` | até 8 trimestres: `{trimestre, indice, reclamacoes}` |
| `idss` | Índice de Desempenho da Saúde Suplementar (0 a 1, maior é melhor) do último ano publicado: `valor`, `ano`, `ano_base`, as 4 `dimensoes` e a `mediana_mesma_modalidade`; com `valor` `null`, o `motivo` |
| `ressarcimento` | ressarcimento ao SUS (quando um cliente da operadora é atendido no SUS, a operadora deve pagar): `indice_pagamento` é o % do valor cobrado que foi pago, acumulado e nos últimos 5 anos, na `competencia` |
| `portabilidade_vigente` | lista de `{ro, data, link}` quando os clientes podem trocar de plano sem cumprir carência de novo |
| `eventos` | cancelamento, registro, direção técnica e portabilidade: `{tipo, id, data, titulo}`, do mais recente ao mais antigo |
| `fontes` | URL de cada conjunto de dados usado |
| `feed` | URL do feed Atom da operadora (`/operadora/<registro>.xml`): os eventos, uma entrada por trimestre de reclamações e uma por ano do IDSS; as entradas apontam para `https://saude.abelhaninja.de/plano/<registro>/` |
| `fora` | indicadores que existem mas a ANS parou de atualizar |

## `todas.json`

`{date, operadoras: [...]}`, em que `date` é o dia dos dados (o mesmo do `meta.json`) e cada item é
exatamente o conteúdo do `operadora/<registro>.json` correspondente, na ordem do índice. É para quem
precisa de tudo de uma vez; para uma operadora só, use o arquivo individual.

## O que fica de fora, e por quê

- **Classificação prudencial (S1–S4):** é um segmento por porte e perfil de risco, usado pela ANS para
  regras de capital; não é nota de saúde financeira.
- **`PORCENTAGEM_HC`** (ressarcimento): significado não verificado.
- **Taxa de resolutividade, garantia de atendimento e penalidades:** a ANS parou de atualizar (ver `fora`).
- **Contatos** do cadastro (e-mail, telefone, representante): não são publicados aqui.
