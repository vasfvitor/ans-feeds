from collections import Counter
from datetime import date, datetime

import pytest
from conftest import SNAPSHOTS, write_day

from ans_feeds import portabilidade

PAGINA = SNAPSHOTS / "2026-10-22" / portabilidade.PAGINA


def test_tables_and_update_date():
    linhas, atualizado = portabilidade.ler(PAGINA)
    assert Counter(linha.situacao for linha in linhas) == {
        "vigente": 14,
        "encerrada": 105,
        "extraordinária encerrada": 18,
    }
    assert atualizado == datetime(2026, 2, 24, 15, 8)
    assert not [ro for ro, n in Counter(linha.ro for linha in linhas).items() if n > 1]


def test_ro_comes_from_its_column_not_from_the_link_text():
    linhas, _ = portabilidade.ler(PAGINA)
    (linha,) = [x for x in linhas if x.ro == "2413"]
    assert linha.data == date(2019, 4, 29)
    assert linha.situacao == "extraordinária encerrada"
    assert linha.link.startswith("http://www.ans.gov.br/component/legislacao/")


def test_normalizar():
    assert portabilidade.normalizar("Porto Alegre Clínicas Ltda (RS)") == "PORTO ALEGRE CLINICAS"
    assert portabilidade.normalizar("MAIS SAUDE S/A") == portabilidade.normalizar("Mais Saúde S.A.")
    assert (
        portabilidade.normalizar("UNIVIDA USA OPERADORA EM SAUDE S/A - EM LIQUIDAÇÃO EXTRAJUDICIAL")
        == "UNIVIDA USA OPERADORA EM SAUDE"
    )


def test_registration_written_in_the_name():
    nome = "Hospital de Caridade de Vargem Grande do Sul – registro ANS nº 36.311-1."
    assert portabilidade.casar(nome, {}, {}) == "363111"


def test_events_and_match_rate():
    eventos, atualizado = portabilidade.portabilidades(SNAPSHOTS)
    assert len(eventos) == 137 and atualizado
    por_ro = {e.chave: e for e in eventos}
    assert por_ro["3094"].data == date(2026, 2, 24)
    assert por_ro["3094"].registro == "422151"
    vigentes = [e for e in eventos if e.detalhes["Situação"] == "vigente"]
    assert sum(1 for e in vigentes if e.registro) >= 13
    # Measured on 2026-10-22: 95 of 137 rows match the CADOP exactly (the rest are old rows whose
    # legal name changed); a drop means the normalization broke.
    assert sum(1 for e in eventos if e.registro) >= 95


def test_a_page_that_reads_as_empty_after_a_full_one_fails_the_build(tree):
    # a redesigned page parses to no rows: publishing that would drop every portability warning
    write_day(tree, "2026-10-22", {portabilidade.PAGINA: PAGINA.read_bytes()})
    write_day(tree, "2026-10-23", {portabilidade.PAGINA: "<html><body>nova página</body></html>"})
    with pytest.raises(RuntimeError, match="no rows, while the version of 2026-10-22"):
        portabilidade.portabilidades(tree)
