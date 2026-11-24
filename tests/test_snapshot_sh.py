"""The Snapshot step of feeds.yml and scripts/snapshot.sh, run as the workflow runs them over
several days, with a fake `curl` first on PATH: the first failure day (desde) of each source must
survive a run that stops halfway.

The fake curl answers by mode (FAKE_CURL):
- govbr: www.gov.br resets the connection (exit 35, as from GitHub's runners since 2026-11-21); the
  FTP answers 304 and its directories list one file of each kind;
- parou: as govbr, but a file download leaves no header file, so snapshot.sh stops halfway;
- ok: everything answers, and the RN 623 page links one PDF.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ans_feeds.site import PAROU

REPO = Path(__file__).resolve().parent.parent

FAKE_CURL = r"""#!/usr/bin/env bash
saida= cabecalhos= formato= url=
while [ $# -gt 0 ]; do
  case $1 in
    -o) saida=$2; shift 2 ;;
    -D) cabecalhos=$2; shift 2 ;;
    -w) formato=$2; shift 2 ;;
    -A|-H|--max-time) shift 2 ;;
    -*) shift ;;
    *) url=$1; shift ;;
  esac
done
codigo() { [ -n "$formato" ] && printf '%s' "$1"; }
case $url in
  https://www.gov.br/*)
    if [ "$FAKE_CURL" != ok ]; then
      echo "curl: (35) Recv failure: Connection reset by peer" >&2
      codigo 000
      exit 35
    fi
    if [ -z "$cabecalhos" ]; then  # the RN 623 page
      echo '<a href="https://www.gov.br/ans/pt-br/Lista_OPS_1T2026.pdf">x</a>' > "$saida"
      codigo 200
      exit 0
    fi ;;
  */)  # an FTP directory
    printf '%s\n' '<a href="202610_Indice_de_Efetivo_Pagamento.csv">' '<a href="HC_2026.csv">' \
      '<a href="pda-020-historico-idss-2016_2025.csv">' > "$saida"
    codigo 200
    exit 0 ;;
esac
if [ "$FAKE_CURL" = parou ]; then  # no header file: snapshot.sh dies reading it
  codigo 200
  exit 0
fi
printf 'HTTP/1.1 304 Not Modified\r\n\r\n' > "$cabecalhos"
codigo 304
"""


def passo_snapshot() -> tuple[str, str]:
    """The `run` script of feeds.yml's Snapshot step, dedented, and its PAROU value."""
    linhas = (REPO / ".github/workflows/feeds.yml").read_text(encoding="utf-8").splitlines()
    i = linhas.index("      - id: snapshot")
    parou = next(x for x in linhas[i:] if x.strip().startswith("PAROU: ")).split(": ", 1)[1]
    i = next(j for j in range(i, len(linhas)) if linhas[j].strip() == "run: |")
    recuo = len(linhas[i]) - len(linhas[i].lstrip()) + 2
    corpo = []
    for linha in linhas[i + 1 :]:
        if linha.strip() and len(linha) - len(linha.lstrip()) < recuo:
            break
        corpo.append(linha[recuo:])
    return "\n".join(corpo) + "\n", parou


@pytest.fixture
def workflow(tmp_path):
    if not shutil.which("bash"):
        pytest.skip("needs bash")
    (tmp_path / "scripts").mkdir()
    shutil.copy(REPO / "scripts/snapshot.sh", tmp_path / "scripts/snapshot.sh")
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "bin").mkdir()
    curl = tmp_path / "bin/curl"
    curl.write_text(FAKE_CURL, encoding="utf-8")
    curl.chmod(0o755)
    (tmp_path / "runner").mkdir()
    script, parou = passo_snapshot()
    assert parou == PAROU  # the row the site knows

    def run(dia: str, modo: str) -> tuple[list[list[str]], str]:
        saida = tmp_path / "runner/output"
        saida.write_text("", encoding="utf-8")
        env = {
            **os.environ,
            "PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "FAKE_CURL": modo,
            "DAY": dia,
            "PAROU": parou,
            "FALHAS_ANTERIOR": str(tmp_path / "runner/FALHAS.anterior.tsv"),
            "GITHUB_OUTPUT": str(saida),
        }
        # GitHub's default shell for run steps
        subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
            cwd=tmp_path,
            env=env,
            check=True,
            capture_output=True,
        )
        falhas = (tmp_path / "snapshots/FALHAS.tsv").read_text(encoding="utf-8").splitlines()
        return [linha.split("\t") for linha in falhas], saida.read_text(encoding="utf-8")

    return run


RN623 = "listas RN 623"
PAGINA = "portabilidade-especial.html"
RESET = "erro 35 do curl"


def test_desde_survives_a_run_that_stops_halfway(workflow):
    falhas, saida = workflow("2026-11-21", "govbr")
    assert falhas == [
        ["2026-11-21", RN623, RESET, "2026-11-21"],
        ["2026-11-21", PAGINA, RESET, "2026-11-21"],
    ]
    assert "failed=true" in saida and "parou" not in saida

    # stopped halfway: no source of its own, so the previous rows stay, with their day and desde
    falhas, saida = workflow("2026-11-22", "parou")
    assert falhas == [
        ["2026-11-22", PAROU, "snapshot.sh terminou com erro sem dizer qual fonte", "2026-11-22"],
        ["2026-11-21", RN623, RESET, "2026-11-21"],
        ["2026-11-21", PAGINA, RESET, "2026-11-21"],
    ]
    assert "parou=true" in saida

    # failing again: the run of failures started on 2026-11-21, not on this day
    falhas, _ = workflow("2026-11-23", "govbr")
    assert falhas == [
        ["2026-11-23", RN623, RESET, "2026-11-21"],
        ["2026-11-23", PAGINA, RESET, "2026-11-21"],
    ]

    # two stops in a row carry the same rows, and only one PAROU row
    workflow("2026-11-24", "parou")
    falhas, _ = workflow("2026-11-25", "parou")
    assert [f[:2] for f in falhas] == [
        ["2026-11-25", PAROU],
        ["2026-11-23", RN623],
        ["2026-11-23", PAGINA],
    ]
    assert {f[3] for f in falhas[1:]} == {"2026-11-21"}

    # a run where every source answers ends the run of failures; the next failure starts another
    falhas, saida = workflow("2026-11-26", "ok")
    assert falhas == [] and "failed" not in saida
    falhas, _ = workflow("2026-11-27", "govbr")
    assert {f[3] for f in falhas} == {"2026-11-27"}
