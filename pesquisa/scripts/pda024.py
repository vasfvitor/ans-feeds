"""Beneficiários por município (PDA-024): totais por abrangência, contratação e cobertura, e, por
município, quantas operadoras têm clientes ali e quantas têm 100 ou mais.

Só biblioteca padrão. Rodar com `python3 -I pesquisa/scripts/pda024.py pda-024-icb-UF-AAAA_MM.csv`
(o CSV de dentro do ZIP).
"""

import collections
import csv
import sys

CORTE = 100


def main(path):
    por_mun = collections.defaultdict(collections.Counter)
    nomes = {}
    abrangencia, contratacao, cobertura = (collections.Counter() for _ in range(3))
    total = 0
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            n = int(r["QT_BENEFICIARIO_ATIVO"])
            total += n
            por_mun[r["NM_MUNICIPIO"]][r["CD_OPERADORA"]] += n
            nomes[r["CD_OPERADORA"]] = r["NM_RAZAO_SOCIAL"]
            abrangencia[r["DE_ABRG_GEOGRAFICA_PLANO"]] += n
            contratacao[r["DE_CONTRATACAO_PLANO"]] += n
            cobertura[r["COBERTURA_ASSIST_PLAN"]] += n
    print(f"beneficiários ativos: {total}; operadoras: {len(nomes)}; municípios: {len(por_mun)}")
    for nome, c in (
        ("abrangência", abrangencia),
        ("contratação", contratacao),
        ("cobertura", cobertura),
    ):
        print(nome, [(k, round(100 * v / total, 1)) for k, v in c.most_common()])
    print(f"município | beneficiários | operadoras com clientes | com {CORTE} ou mais | de 1 a 9")
    linhas = sorted(por_mun.items(), key=lambda kv: -sum(kv[1].values()))
    for mun, ops in linhas:
        valores = [v for v in ops.values() if v > 0]
        print(
            f"  {mun} | {sum(valores)} | {len(valores)} | {sum(v >= CORTE for v in valores)}"
            f" | {sum(v < 10 for v in valores)}"
        )
    mun, ops = linhas[0]
    print(f"{mun}, as 8 maiores:", [(nomes[o], v) for o, v in ops.most_common(8)])


if __name__ == "__main__":
    main(sys.argv[1])
