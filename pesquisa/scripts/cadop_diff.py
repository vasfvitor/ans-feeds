"""Diff de dois snapshots do CADOP (ativas e canceladas): entradas, saídas e campos alterados por registro.

Só biblioteca padrão. Rodar com `python3 -I pesquisa/scripts/cadop_diff.py SNAPSHOT_ANTIGO SNAPSHOT_NOVO`.
"""

import collections
import csv
import sys


def ler(pasta, arq):
    with open(f"{pasta}/{arq}", encoding="utf-8", newline="") as f:
        return {r["REGISTRO_OPERADORA"]: r for r in csv.DictReader(f, delimiter=";")}


def main():
    antigo, novo = (p.rstrip("/") for p in sys.argv[1:3])
    for arq in ("Relatorio_cadop.csv", "Relatorio_cadop_canceladas.csv"):
        a, n = ler(antigo, arq), ler(novo, arq)
        entraram = sorted(n.keys() - a.keys())
        sairam = sorted(a.keys() - n.keys())
        mudou = collections.Counter()
        exemplos = []
        alterados = 0
        for reg in sorted(a.keys() & n.keys()):
            campos = [c for c in n[reg] if a[reg].get(c) != n[reg][c]]
            mudou.update(campos)
            alterados += bool(campos)
            if campos and len(exemplos) < 10:
                exemplos.append((reg, {c: (a[reg].get(c), n[reg][c]) for c in campos}))
        print(f"### {arq}: {len(a)} → {len(n)}; entraram {len(entraram)}, saíram {len(sairam)}, alterados {alterados}")
        for reg in entraram:
            r = n[reg]
            print(f"  + {reg} {r['RAZAO_SOCIAL'][:50]} {r.get('DATA_DESCREDENCIAMENTO', r['DATA_REGISTRO_ANS'])} {r.get('MOTIVO_DO_DESCREDENCIAMENTO', '')}")
        for reg in sairam:
            print(f"  - {reg} {a[reg]['RAZAO_SOCIAL'][:50]}")
        print("  campos alterados:", dict(mudou))
        for reg, d in exemplos:
            print(f"  ~ {reg} {d}")


main()
