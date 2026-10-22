"""Reconstrói as listas trimestrais da RN 623 (Excelência e Redução) a partir do pda-023-igr.csv.

Entrada: o CSV do IGR e as saídas de `pdftotext -bbox` dos PDFs oficiais. Só biblioteca padrão.
Rodar com `python3 -I pesquisa/scripts/rn623.py IGR.csv EXC_MH.html EXC_OD.html RED_MH.html RED_OD.html`.
"""

import collections
import csv
import re
import sys

NUM = re.compile(r"^\d+(\.\d{3})*(,\d+)?$")
TRIMESTRES = {"4T2025": ("2025-10", "2025-11", "2025-12"),
              "1T2026": ("2026-01", "2026-02", "2026-03"),
              "2T2026": ("2026-04", "2026-05", "2026-06")}
COB = {"MH": "Assistência médica", "OD": "Exclusivamente odontológica"}


def palavras(caminho):
    t = open(caminho, encoding="utf-8").read()
    for n, pag in enumerate(t.split("<page ")[1:]):
        for x0, y0, x1, w in re.findall(r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="[\d.]+">([^<]*)<', pag):
            yield n, float(x0), float(y0), float(x1), w


def ler_pdf(caminho, ncols):
    """Linhas {registro: [valores por coluna]}; colunas numéricas achadas por agrupamento dos centros."""
    ws = list(palavras(caminho))
    regs = sorted((p, y, w) for p, x0, y, x1, w in ws if re.fullmatch(r"\d{6}", w) and x0 < 100)
    nums = []
    for p, x0, y, x1, w in ws:
        if x0 > 200 and NUM.match(w):
            dono = [(ry, r) for rp, ry, r in regs if rp == p and ry <= y + 1.5]
            if dono and y - dono[-1][0] < 30:
                nums.append((dono[-1][1], (x0 + x1) / 2, w))
    centros = sorted(c for _, c, _ in nums)
    grupos = [[centros[0]]]
    for c in centros[1:]:
        (grupos[-1] if c - grupos[-1][-1] < 8 else grupos.append([c]) or grupos[-1]).append(c)
    grupos = sorted(grupos, key=len, reverse=True)[:ncols]
    cols = sorted(sum(g) / len(g) for g in grupos)
    linhas = {r: [None] * ncols for _, _, r in regs}
    for dono, c, w in nums:
        i = min(range(ncols), key=lambda k: abs(cols[k] - c))
        if abs(cols[i] - c) < 12 and linhas[dono][i] is None:
            linhas[dono][i] = w
    return linhas


def valor(s):
    return None if s is None else float(s.replace(".", "").replace(",", "."))


def igr_trimestral(igr, reg, cob, tri):
    meses = [igr.get((reg, COB[cob], m)) for m in TRIMESTRES[tri]]
    meses = [m for m in meses if m]
    if not meses:
        return None
    nip = sum(q for q, _ in meses)
    benef = sum(b for _, b in meses) / len(meses)
    return nip, benef, (nip / 3) / benef * 100000 if benef else None, len(meses)


def comparar(nome, linhas, igr, blocos):
    """blocos: [(cobertura, trimestre, i_nip, i_benef ou None, i_igr)]."""
    print(f"\n### {nome}: {len(linhas)} operadoras no PDF")
    for cob, tri, i_nip, i_ben, i_igr in blocos:
        tot = bate_nip = bate_ben = bate_igr = 0
        difs = []
        desvios = []
        for reg, v in sorted(linhas.items()):
            if v[i_nip] is None:
                continue
            tot += 1
            calc = igr_trimestral(igr, reg, cob, tri)
            if not calc:
                difs.append((reg, "ausente do CSV", v[i_nip], v[i_igr]))
                continue
            nip, ben, ind, n = calc
            ok_nip = nip == valor(v[i_nip])
            ok_ben = i_ben is None or round(ben) == valor(v[i_ben])
            if i_ben is not None and valor(v[i_ben]):
                desvios.append(abs(ben - valor(v[i_ben])) / valor(v[i_ben]))
            ok_igr = ind is not None and v[i_igr] is not None and abs(round(ind, 2) - valor(v[i_igr])) < 0.011
            bate_nip += ok_nip
            bate_ben += ok_ben
            bate_igr += ok_igr
            if not (ok_nip and ok_igr):
                difs.append((reg, f"CSV nip={nip} benef={ben:.1f} igr={ind if ind is None else round(ind, 2)} meses={n}",
                             f"PDF nip={v[i_nip]} benef={v[i_ben] if i_ben is not None else '-'} igr={v[i_igr]}"))
        print(f"{cob} {tri}: linhas={tot} NIP igual={bate_nip} média benef. igual={bate_ben} IGR igual (±0,01)={bate_igr}")
        if desvios:
            desvios.sort()
            print(f"    desvio relativo da média de benef. CSV × PDF: mediana={desvios[len(desvios) // 2]:.4%} "
                  f"p90={desvios[int(len(desvios) * .9)]:.4%} máx={desvios[-1]:.4%}")
        for d in difs[:8]:
            print("   ", *d)
        if len(difs) > 8:
            print(f"    … mais {len(difs) - 8}")


def main():
    arq_igr, exc_mh, exc_od, red_mh, red_od = sys.argv[1:6]
    igr = {}
    nomes = {}
    with open(arq_igr, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            igr[(r["REGISTRO_OPERADORA"], r["COBERTURA"], r["COMPETENCIA"])] = (int(r["QTD_RECLAMACOES"]), int(r["QTD_BENEFICIARIOS"]))
            nomes[r["REGISTRO_OPERADORA"]] = r["RAZAO_SOCIAL"]

    em = ler_pdf(exc_mh, 6)
    eo = ler_pdf(exc_od, 3)
    comparar("Excelência MH 2T2026", em, igr, [("MH", "2T2026", 0, 1, 2), ("OD", "2T2026", 3, 4, 5)])
    comparar("Excelência OD 2T2026", eo, igr, [("OD", "2T2026", 0, 1, 2)])
    rm = ler_pdf(red_mh, 12)
    ro = ler_pdf(red_od, 6)
    comparar("Redução MH 2T2026", rm, igr,
             [(c, t, i0 + k, None, i0 + 3 + k) for c, i0 in (("MH", 0), ("OD", 6)) for k, t in enumerate(TRIMESTRES)])
    comparar("Redução OD 2T2026", ro, igr, [("OD", t, k, None, 3 + k) for k, t in enumerate(TRIMESTRES)])

    # Reconstrução da lista de Excelência só pelo critério de IGR (meta MH 2,4 / OD 0,6, ou ≤3 / ≤2 NIPs).
    ops = {r for r, _, m in igr if m in TRIMESTRES["2T2026"]}
    oficiais = set(em) | set(eo)

    def prever(meta_mh, meta_od):
        previstos = set()
        for reg in ops:
            ok = True
            tem = False
            for cob, meta, atalho in (("MH", meta_mh, 3), ("OD", meta_od, 2)):
                calc = igr_trimestral(igr, reg, cob, "2T2026")
                if calc:
                    tem = True
                    nip, _, ind, _ = calc
                    ok &= nip <= atalho or (ind is not None and round(ind, 2) <= meta)
            if tem and ok:
                previstos.add(reg)
        return previstos

    print("\n### Sensibilidade da meta (Excelência 2T2026): previstos, acertos, falsos positivos")
    for mh, od in ((2.4, 0.6), (0, 0), (30.5, 30.5), (60.9, 60.9), (24, 6)):
        p = prever(mh, od)
        print(f"meta MH={mh} OD={od}: previstos={len(p)} nos dois={len(p & oficiais)} só previstos={len(p - oficiais)}")

    print("\n### Excelência 2T2026 reconstruída só pelo critério do IGR (Anexo II: meta ou atalho, cumulativo MH e OD)")
    previstos = prever(2.4, 0.6)
    print(f"previstos={len(previstos)} oficiais (MH ∪ OD)={len(oficiais)} nos dois={len(previstos & oficiais)} "
          f"só previstos={len(previstos - oficiais)} só oficiais={len(oficiais - previstos)}")
    print("só oficiais:", sorted(oficiais - previstos)[:20])
    so_prev = sorted(previstos - oficiais)
    ben = collections.Counter()
    for reg in so_prev:
        b = max((igr_trimestral(igr, reg, c, "2T2026") or (0, 0, 0, 0))[1] for c in COB)
        ben["<100" if b < 100 else "<1000" if b < 1000 else "≥1000"] += 1
    print("só previstos, por porte (média benef.):", dict(ben))
    print("exemplos só previstos:", [(r, nomes.get(r, "")[:30]) for r in so_prev[:10]])


main()
