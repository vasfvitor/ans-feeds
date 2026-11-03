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
| feeds / snapshot | `FALHA:`, `HTTP`, `fora do ar`, `nenhum` | [Fonte da ANS falhou](#fonte-da-ans-falhou) |
| feeds / snapshot | `bytes contra`, `na versão anterior` | [Arquivo da ANS encolheu](#arquivo-da-ans-encolheu) |
| feeds / snapshot | `Traceback` em "CADOP diff" | [Diff do CADOP quebrou](#diff-do-cadop-quebrou) |
| feeds / snapshot | `git push`, `CONFLICT` | [Commit do snapshot falhou](#commit-do-snapshot-falhou) |
| feeds / build | `changed layout`, `portabilidade.ler needs a fix` | [Página de portabilidade mudou](#página-de-portabilidade-mudou) |
| feeds / build | `Traceback`, `KeyError`, `UnicodeDecodeError` | [Um arquivo da ANS mudou de formato](#um-arquivo-da-ans-mudou-de-formato) |
| feeds / deploy | `the CADOP has no Last-Modified or has not changed` | [CADOP parado na ANS](#cadop-parado-na-ans) |
| feeds / deploy | `the portal could not be read or is more than 2 days behind` | [Portal atrasado](#portal-atrasado) |
| ci | ruff, pytest, build | [Lint, formato ou testes](#lint-formato-ou-testes) |

## feeds

Roda todo dia às 10:30 UTC (07:30 em Brasília), meia hora depois de a ANS publicar o CADOP. Também roda,
só com build, quando um push muda `src/`, `pyproject.toml`, `uv.lock` ou o próprio workflow. Tem três
jobs:

1. **snapshot:** `scripts/snapshot.sh` baixa o que a ANS sobrescreve (CADOP, IGR, RN 623, portabilidade,
   ressarcimento ao SUS, IDSS) e faz commit só do que mudou, em `snapshots/AAAA-MM-DD/`.
2. **build:** monta o site a partir dos snapshots. Roda mesmo quando o snapshot falhou.
3. **deploy:** publica no Pages e, depois, confere a idade do CADOP e o atraso do portal.

Uma fonte fora do ar não impede as outras: o que foi baixado é commitado e só então o job fica vermelho.

**Para rodar de novo:** Actions → feeds → "Run workflow" no `main`. Não use "Re-run jobs": ele parte do
commit antigo e o `git pull --rebase` do snapshot do dia entra em conflito. Com `build_only` marcado, ele
só remonta o site, sem baixar nada.

### Fonte da ANS falhou

- **Onde aparece:** job snapshot. No passo Snapshot, a linha `FALHA: <fonte> (<motivo>)`. O job só fica
  vermelho no último passo, "Fail if a source failed (after committing the rest)", que não imprime
  mensagem própria.
- **Motivos possíveis:**
  - `HTTP <código>`: `HTTP 000` quer dizer erro de rede ou tempo esgotado;
  - `página fora do ar` ou `nenhum PDF na página` (listas da RN 623);
  - `diretório fora do ar` ou `nenhum arquivo no diretório` (ressarcimento, IDSS).
- **O que quer dizer:** essa fonte não respondeu como devia. Ela fica com a versão anterior; as outras
  foram baixadas e commitadas.
- **O site foi afetado?** Saiu com a versão anterior dessa fonte e o aviso "A coleta de hoje falhou em
  parte; estes dados são da última coleta bem-sucedida de cada fonte." O `meta.json` lista a fonte em
  `falhas`, e o portal mostra que esses números são da coleta anterior.
- **Agir ou esperar:** esperar. O run do dia seguinte tenta de novo.
- **Pedir ajuda quando:** a mesma fonte falhar por mais de uma semana, ou o motivo for `nenhum PDF na
  página` ou `nenhum arquivo no diretório` vários dias seguidos (a ANS pode ter mudado o endereço).

### Arquivo da ANS encolheu

- **Onde aparece:** job snapshot, passo Snapshot.
- **Mensagem:** `FALHA: <fonte> (N bytes contra M na versão anterior)`
- **O que quer dizer:** o arquivo novo tem menos da metade do tamanho do anterior. Pode ser um arquivo
  cortado ou uma página de erro. O script guarda a versão anterior e o job fica vermelho.
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

- **Onde aparece:** job deploy, passo "Check the CADOP's age and the portal's lag", depois do deploy.
- **Mensagem:** `::error::the CADOP has no Last-Modified or has not changed at the ANS for N days`
- **O que quer dizer:** a ANS publica o CADOP todo dia, e ele não muda há mais de 7 dias.
- **O site foi afetado?** Não quebrou. Mostra o último CADOP publicado, só que velho.
- **Agir ou esperar:** esperar. A causa está na ANS (um feriado longo também pode causar isso).
- **Pedir ajuda quando:** a ANS voltou a publicar e o alarme continua.

### Portal atrasado

- **Onde aparece:** o mesmo passo, depois do deploy.
- **Mensagem:** `::error::the portal could not be read or is more than 2 days behind <data>`
- **O que quer dizer:** o portal (saude.abelhaninja.de) lê os dados deste repo e está mais de 2 dias
  atrás, ou o `build.json` dele não abriu. O problema está no portal, não aqui. Este alarme fica aqui
  porque o cron do portal pode ser desligado pelo GitHub sem que nada mais avise.
- **O site foi afetado?** Este site não. O portal está com dados velhos.
- **O que fazer:** abrir o
  [RUNBOOK do portal-saude](https://github.com/vasfvitor/portal-saude/blob/main/RUNBOOK.md) e ver o
  último run do workflow de publicação de lá.

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
  o `FALHAS.tsv` e o `ESTADO.tsv` não são reescritos, e as falhas do dia anterior aparecem de novo. Fase
  3.
- **Arquivo que encolheu de verdade não tem saída.** Ver
  [Arquivo da ANS encolheu](#arquivo-da-ans-encolheu).
- **A data do site só anda quando algum arquivo muda.** Num dia em que nada mudou na ANS, a data continua
  a do último snapshot.
