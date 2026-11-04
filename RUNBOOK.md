# RUNBOOK do ans-feeds

O que fazer quando um workflow deste repo fica vermelho. Comece pelo
[RUNBOOK do anvisa-hub](https://github.com/vasfvitor/anvisa-hub/blob/main/RUNBOOK.md): lá estão o mapa
dos seis repos, a rotina e o que vale para todos (rodar de novo, run cinza, lockfile, Pages).

As mensagens aparecem aqui como o log mostra. Procure com Ctrl+F um trecho da mensagem que você viu.
`<fonte>`, `N` e afins marcam a parte que muda.

Quem cria ou muda um alarme ou uma mensagem de erro atualiza este arquivo no mesmo commit.

## Índice

| Workflow / job | Trecho da mensagem | Entrada |
|---|---|---|
| feeds / snapshot | issue "Fonte da ANS falhou", `FALHA:`, `HTTP`, `fora do ar`, `nenhum` | [Fonte da ANS falhou](#fonte-da-ans-falhou) |
| feeds / snapshot | `stopped halfway` | [Coleta parou no meio](#coleta-parou-no-meio) |
| feeds / snapshot | `bytes contra`, `na versão anterior` | [Arquivo da ANS encolheu](#arquivo-da-ans-encolheu) |
| feeds / snapshot | `Traceback` em "CADOP diff" | [Diff do CADOP quebrou](#diff-do-cadop-quebrou) |
| feeds / snapshot | `git push`, `CONFLICT` | [Commit do snapshot falhou](#commit-do-snapshot-falhou) |
| feeds / build | `changed layout`, `portabilidade.ler needs a fix` | [Página de portabilidade mudou](#página-de-portabilidade-mudou) |
| feeds / build | `Traceback`, `KeyError`, `UnicodeDecodeError` | [Um arquivo da ANS mudou de formato](#um-arquivo-da-ans-mudou-de-formato) |
| feeds / deploy | issue "CADOP parado na ANS", `the CADOP has no Last-Modified` | [CADOP parado na ANS](#cadop-parado-na-ans) |
| feeds / deploy | issue "Portal N dias atrás" ou "O build.json do portal não abriu", `this site's meta.json has no date` | [Portal atrasado](#portal-atrasado) |
| ci | ruff, pytest, build | [Lint, formato ou testes](#lint-formato-ou-testes) |

## feeds

Roda todo dia às 10:30 UTC (07:30 em Brasília), meia hora depois de a ANS publicar o CADOP. Também roda,
só com build, quando um push muda `src/`, `pyproject.toml`, `uv.lock` ou o próprio workflow. Tem três
jobs:

1. **snapshot:** `scripts/snapshot.sh` baixa o que a ANS sobrescreve (CADOP, IGR, RN 623, portabilidade,
   ressarcimento ao SUS, IDSS) e faz commit só do que mudou, em `snapshots/AAAA-MM-DD/`.
2. **build:** monta o site a partir dos snapshots. Roda mesmo quando o snapshot falhou.
3. **deploy:** publica no Pages e, depois, confere a idade do CADOP e o atraso do portal.

Uma fonte fora do ar não impede as outras: o que foi baixado é commitado.

Três causas de fora do código não deixam o run vermelho: abrem uma issue com o label `alerta`, que fecha
sozinha quando a situação normaliza (ver o RUNBOOK do hub, "Issues de alerta"). São elas: uma fonte da
ANS que falhou, o CADOP parado e o portal atrasado. O run fica verde, com um aviso amarelo.

**Para rodar de novo:** Actions → feeds → "Run workflow" no `main`. Não use "Re-run jobs": ele parte do
commit antigo e o `git pull --rebase` do snapshot do dia entra em conflito. Com `build_only` marcado, ele
só remonta o site, sem baixar nada.

### Fonte da ANS falhou

- **Onde aparece:** a issue "Fonte da ANS falhou: N fontes com a versão anterior", aberta pelo job
  snapshot (passo "Alarm issue for the sources that failed"). O run fica verde. No log do passo
  Snapshot, a linha `FALHA: <fonte> (<motivo>)`.
- **Motivos possíveis:**
  - `HTTP <código>`: `HTTP 000` quer dizer erro de rede ou tempo esgotado;
  - `página fora do ar` ou `nenhum PDF na página` (listas da RN 623);
  - `diretório fora do ar` ou `nenhum arquivo no diretório` (ressarcimento, IDSS).
- **O que quer dizer:** essa fonte não respondeu como devia. Ela fica com a versão anterior; as outras
  foram baixadas e commitadas.
- **O site foi afetado?** Saiu com a versão anterior dessa fonte e o aviso "A coleta de hoje falhou em
  parte; estes dados são da última coleta bem-sucedida de cada fonte." O `meta.json` lista a fonte em
  `falhas`, e o portal mostra que esses números são da coleta anterior.
- **Agir ou esperar:** esperar. O run do dia seguinte tenta de novo, e a issue fecha sozinha no primeiro
  dia sem falha.
- **Pedir ajuda quando:** a issue ficar aberta por mais de uma semana, ou o motivo for `nenhum PDF na
  página` ou `nenhum arquivo no diretório` vários dias seguidos (a ANS pode ter mudado o endereço).

### Coleta parou no meio

- **Onde aparece:** job snapshot, passo "List the sources that failed". Fica vermelho.
- **Mensagem:** `::error::snapshot.sh failed with no source in FALHAS.tsv for <dia>: it stopped halfway`
- **O que quer dizer:** o `snapshot.sh` terminou com erro, mas sem registrar nenhuma fonte que falhou
  naquele dia. Ele parou no meio por um erro inesperado, um problema no script.
- **O site foi afetado?** O que foi baixado antes do erro pode ter sido commitado. O site sai com o aviso
  de coleta com falha.
- **Agir ou esperar:** pedir ajuda. O log do passo Snapshot mostra onde ele parou.

### Arquivo da ANS encolheu

- **Onde aparece:** a issue "Fonte da ANS falhou", com o motivo abaixo. No log do passo Snapshot, a
  mesma linha.
- **Mensagem:** `FALHA: <fonte> (N bytes contra M na versão anterior)`
- **O que quer dizer:** o arquivo novo tem menos da metade do tamanho do anterior. Pode ser um arquivo
  cortado ou uma página de erro. O script guarda a versão anterior.
- **O site foi afetado?** Não. Segue com a versão anterior.
- **Agir ou esperar:** esperar um dia.
- **Pedir ajuda quando:** repetir. Se a ANS diminuiu o arquivo de verdade, não há como liberar à mão: o
  script precisa mudar. Até lá, essa fonte não atualiza.

### Diff do CADOP quebrou

- **Onde aparece:** job snapshot, passo "CADOP diff against the previous snapshot", com um `Traceback`
  (por exemplo, `KeyError` ou `UnicodeDecodeError`).
- **O que quer dizer:** o CADOP novo veio com outro cabeçalho ou outra codificação.
- **O site foi afetado?** O dia não foi guardado: os passos de artifact e de commit não rodam depois
  desse erro. O build segue com os snapshots anteriores e o aviso de coleta com falha.
- **Agir ou esperar:** pedir ajuda. O run seguinte baixa de novo o que mudou, mas vai quebrar no mesmo
  ponto enquanto o formato for o novo.

### Commit do snapshot falhou

- **Onde aparece:** job snapshot, passo "Commit and push the snapshot", com uma saída do `git` (por
  exemplo, `CONFLICT`).
- **O que quer dizer:** o snapshot foi baixado, mas não chegou ao `main`.
- **O que fazer:** o snapshot fica guardado 90 dias como artifact `snapshot-<dia>` na página do run.
  1. Baixar o artifact (página do run → Artifacts).
  2. Colocar a pasta do dia e o `ESTADO.tsv` dentro de `snapshots/`.
  3. Commit e push.
- **Pedir ajuda quando:** não tiver certeza do que ficou no `main`.

### Página de portabilidade mudou

- **Onde aparece:** job build, passo "Build the site".
- **Mensagem:** `RuntimeError: portabilidade-especial.html of <dia>: no rows, while the version of <dia anterior> had some; the page probably changed layout and portabilidade.ler needs a fix`
- **O que quer dizer:** a página de portabilidade especial da ANS veio sem nenhuma linha, e a anterior
  tinha. A ANS provavelmente mudou o layout.
- **O site foi afetado?** Nada foi publicado. O deploy anterior continua.
- **Agir ou esperar:** pedir ajuda. O leitor da página precisa mudar.

### Um arquivo da ANS mudou de formato

- **Onde aparece:** job build, passo "Build the site", com um `Traceback` (`KeyError`,
  `UnicodeDecodeError`, `ValueError`).
- **O que quer dizer:** a ANS mudou uma coluna ou a codificação de um dos CSVs.
- **O site foi afetado?** Nada foi publicado. O deploy anterior continua.
- **Agir ou esperar:** pedir ajuda.

### CADOP parado na ANS

- **Onde aparece:** a issue "CADOP parado na ANS há N dias", aberta pelo job deploy depois do deploy. O
  run fica verde. No log do passo "Check the CADOP's age and the portal's lag":
  `the CADOP has not changed at the ANS for N days`.
- **O que quer dizer:** a ANS publica o CADOP todo dia, e ele não muda há mais de 7 dias.
- **O site foi afetado?** Não quebrou. Mostra o último CADOP publicado, só que velho.
- **Agir ou esperar:** esperar. A causa está na ANS (um feriado longo também pode causar isso).
- **Pedir ajuda quando:** a ANS voltou a publicar e a issue não fechou.
- **Vermelho, com `::error::the CADOP has no Last-Modified`:** o build não achou a data do CADOP. Não é
  atraso da ANS, é um problema no snapshot ou no build. Pedir ajuda.

### Portal atrasado

- **Onde aparece:** a issue "Portal N dias atrás dos dados da ANS" ou "O build.json do portal não
  abriu", aberta pelo mesmo passo. O run fica verde. No log:
  `the portal could not be read or is more than 2 days behind <data>`.
- **O que quer dizer:** o portal (saude.abelhaninja.de) lê os dados deste repo e está mais de 2 dias
  atrás, ou o `build.json` dele não abriu. O problema está no portal, não aqui. Este alarme fica aqui
  porque o cron do portal pode ser desligado pelo GitHub sem que nada mais avise.
- **O site foi afetado?** Este site não. O portal está com dados velhos.
- **O que fazer:** abrir o
  [RUNBOOK do portal-saude](https://github.com/vasfvitor/portal-saude/blob/main/RUNBOOK.md) e ver o
  último run do workflow de publicação de lá. A issue fecha sozinha quando o portal alcançar.
- **O `build.json` não abriu:** a leitura já foi tentada quatro vezes, com 10 segundos entre elas. Então
  não é uma oscilação de rede.
- **Vermelho, com `::error::this site's meta.json has no date`:** o problema é deste site, não do portal.
  O build saiu sem a data dos dados, então o atraso não foi medido e a issue do portal não mudou. Pedir
  ajuda.

## ci

Roda em push de pessoa no `main` e em pull request: `uv sync --locked`, `ruff`, `pytest` e um build a
partir dos snapshots commitados. Os commits de snapshot do bot não disparam o `ci`. Não publica nada; o
deploy vem do workflow feeds.

### Lint, formato ou testes

- **O que fazer**, na máquina:

  ```bash
  uv sync
  uv run ruff check . && uv run ruff format .
  uv run pytest
  ```

- **Testes que quebram sozinhos:** vários testes conferem números dos snapshots reais (ver
  [Problemas conhecidos](#problemas-conhecidos)). Quando um deles falha sem que ninguém tenha mudado o
  código, o dado mudou na ANS, não o código. Em 03/11/2026, falharam dois:
  - `test_real_counts_and_no_contact_data`: esperava 1106 operadoras ativas, e o CADOP passou a ter 1105;
  - `test_real_tree`: esperava o último `Relatorio_cadop_canceladas.csv` em `2026-10-22`, e ele está em
    `2026-10-29`.
- **Pedir ajuda quando:** não for um desses casos.

## Problemas conhecidos

Achados em 2026-11-03, ainda sem correção.

- **Testes presos aos dados reais.** Além dos dois acima, há uns seis que conferem valores que a ANS vai
  mudar: o ressarcimento da Abertta (do índice de 202609), o número de eventos e a data da página de
  portabilidade, a portabilidade e o cancelamento da Univida, e as reclamações da Mediservice no 3T2026.
  Fase 3.
- **Diff do CADOP perde o dia.** Ver [Diff do CADOP quebrou](#diff-do-cadop-quebrou). Fase 3.
- **Script que para no meio republica falhas antigas.** Se o `snapshot.sh` parar por um erro inesperado,
  o `ESTADO.tsv` não é reescrito. O workflow percebe isso e fica vermelho (ver
  [Coleta parou no meio](#coleta-parou-no-meio)), e o `meta.json` desse dia sai sem a lista de falhas.
  Fase 3.
- **Arquivo que encolheu de verdade não tem saída.** Ver
  [Arquivo da ANS encolheu](#arquivo-da-ans-encolheu).
- **A data do site só anda quando algum arquivo muda.** Num dia em que nada mudou na ANS, a data continua
  a do último snapshot.
