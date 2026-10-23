import json

import pytest
from conftest import SNAPSHOTS, write_day

from ans_feeds import eventos, operadoras, portabilidade

IGR_HEAD = (
    "REGISTRO_OPERADORA;RAZAO_SOCIAL;COBERTURA;IGR;QTD_RECLAMACOES;QTD_BENEFICIARIOS;"
    "PORTE_OPERADORA;COMPETENCIA;COMPETENCIA_BENEFICIARIO;DT_ATUALIZACAO\n"
)


def igr_row(reg, nips, benef, mes, porte="Pequeno", cob="Assistência médica"):
    return f'"{reg}";"X";"{cob}";0,00;{nips};{benef};"{porte}";"{mes}";"{mes}";"2026-10-07"\n'


def test_numero_and_trimestre():
    assert operadoras.numero("0,8112") == 0.8112
    assert operadoras.numero("91,31%") == 91.31
    assert operadoras.numero("1.234,50") == 1234.5
    assert operadoras.numero("ND") is None and operadoras.numero("") is None
    assert operadoras.trimestre("2026-09") == "3T2026"
    assert operadoras.trimestre("2026-01") == "1T2026"


def test_quarterly_index_and_peer_median(tree):
    linhas = [IGR_HEAD]
    for mes in ("2026-07", "2026-08", "2026-09"):
        linhas += [
            igr_row("000001", 3, 100000, mes),  # (9/3)/100000*1e5 = 3.00
            igr_row("000002", 6, 100000, mes),  # 6.00
            igr_row("000003", 30, 100000, mes),  # 30.00
        ]
    linhas.append(igr_row("000004", 1, 1000, "2026-09"))  # one month only: no quarter
    write_day(tree, "2026-10-22", {operadoras.IGR: "".join(linhas)})
    recl, benef = operadoras.reclamacoes(tree)
    (r,) = recl["000003"]
    assert r["trimestre"] == "3T2026" and r["indice"] == 30.0 and r["reclamacoes"] == 90
    assert r["mediana_mesmo_porte"] == 6.0 and r["operadoras_mesmo_porte"] == 3
    assert r["cobertura"] == "médico-hospitalar"
    assert "000004" not in recl
    assert benef["000001"] == 100000


@pytest.fixture(scope="module")
def reais():
    todos = (
        eventos.cancelamentos(SNAPSHOTS)
        + eventos.registros(SNAPSHOTS)
        + eventos.direcao_tecnica(SNAPSHOTS)
        + portabilidade.portabilidades(SNAPSHOTS)[0]
    )
    return {o["registro"]: o for o in operadoras.operadoras(SNAPSHOTS, todos)}


def test_real_counts_and_no_contact_data(reais):
    assert sum(o["situacao"] == "ativa" for o in reais.values()) == 1106
    texto = json.dumps(list(reais.values()), ensure_ascii=False)
    assert "@" not in texto
    for campo in ("TELEFONE", "telefone", "email", "REPRESENTANTE", "representante"):
        assert campo not in texto


def test_mediservice_by_coverage(reais):
    # Checked by hand in pda-023: 38 + 29 + 48 complaints (médico-hospitalar) in Jul-Sep 2026.
    por_cob = {r["cobertura"]: r for r in reais["333689"]["reclamacoes"]}
    assert por_cob["médico-hospitalar"]["reclamacoes"] == 115
    assert por_cob["médico-hospitalar"]["indice"] == 39.03
    assert por_cob["odontológica"]["reclamacoes"] == 73 + 83 + 115
    assert len(por_cob["médico-hospitalar"]["serie"]) == 8


def test_univida_in_liquidation(reais):
    u = reais["422134"]
    assert u["situacao"] == "cancelada"
    assert u["cancelamento"] == {"data": "2026-09-22", "motivo": "Liquidação Extrajudicial"}
    assert u["portabilidade_vigente"]
    assert u["idss"]["valor"] is None and u["idss"]["motivo"]
    assert any(e["tipo"] == "cancelamento" for e in u["eventos"])


def test_index_matches_records(reais):
    idx = operadoras.indice(list(reais.values()))
    assert len(idx) == len(reais)
    assert set(idx[0]) == {
        "registro",
        "nome",
        "fantasia",
        "uf",
        "municipio",
        "modalidade",
        "situacao",
        "beneficiarios",
    }
