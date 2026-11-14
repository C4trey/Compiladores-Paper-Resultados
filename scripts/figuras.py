#!/usr/bin/env python3
"""Genera las figuras y tablas del artículo a partir de los CSV de resultados/.

Salidas en figuras/:
  fig_matriz.pdf      mapa de calor de PI1 (técnica x nivel, un panel por compilador)
  fig_costo.pdf       costo de cada técnica frente al tamaño (PI3)
  tabla_lto.tex       resultados de PI2 (para \\input en LaTeX)
  tabla_pases.tex     pase responsable de cada eliminación
  tabla_tamano.tex    tamaño de código de victima() con -O2
  resumen.txt         cifras clave para el resumen y las conclusiones
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import NIVELES, RAIZ, RESULTADOS

FIG = os.path.join(RAIZ, "figuras")
os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "font.family": "serif"})
QUEDA = ("vulnerable", "ineficaz")     # el secreto permanece en memoria
lineas_resumen = []


def nota(texto):
    print(texto)
    lineas_resumen.append(texto)


def esc(v):
    """Escapa los caracteres especiales de LaTeX."""
    v = str(v)
    for a, b in [("\\", "\\textbackslash{}"), ("_", "\\_"), ("&", "\\&"), ("%", "\\%"),
                 ("#", "\\#"), ("->", "$\\to$")]:
        v = v.replace(a, b)
    return v


def tabla_latex(df, archivo, columnas_fmt=None):
    cols = columnas_fmt or ("l" * (len(df.columns) + 1))
    with open(os.path.join(FIG, archivo), "w", encoding="utf-8") as f:
        f.write("\\begin{tabular}{@{}" + cols + "@{}}\n\\toprule\n")
        f.write(" & ".join([esc(df.index.name or "")] + [esc(c) for c in df.columns]) + " \\\\\n\\midrule\n")
        for idx, fila in df.iterrows():
            f.write(" & ".join([esc(idx)] + [esc(v) for v in fila.values]) + " \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n")


# ---------------------------------------------------------------------------
# PI1: matriz
# ---------------------------------------------------------------------------
def matriz():
    d = pd.read_csv(os.path.join(RESULTADOS, "matriz.csv"))
    d = d[d.tecnica != "T0"]
    compiladores = list(dict.fromkeys(d.compilador))
    tecnicas = [f"T{i}" for i in range(1, 10)]
    fig, ejes = plt.subplots(1, len(compiladores), figsize=(7.0, 2.6), sharey=True)
    ejes = np.atleast_1d(ejes)
    for ax, cc in zip(ejes, compiladores):
        m = np.full((len(tecnicas), len(NIVELES)), np.nan)
        etiquetas = [["" for _ in NIVELES] for _ in tecnicas]
        for i, t in enumerate(tecnicas):
            for j, nv in enumerate(NIVELES):
                x = d[(d.compilador == cc) & (d.tecnica == t) & (d.nivel == nv)]
                if len(x) == 0 or (x.categoria == "error").all():
                    etiquetas[i][j] = "n/c"
                    continue
                k = x.categoria.isin(QUEDA).sum()
                m[i, j] = k / len(x)
                etiquetas[i][j] = f"{k}/{len(x)}"
        ax.imshow(m, cmap="Reds", vmin=0, vmax=1, aspect="auto")
        for i in range(len(tecnicas)):
            for j in range(len(NIVELES)):
                v = m[i, j]
                ax.text(j, i, etiquetas[i][j], ha="center", va="center", fontsize=6,
                        color="white" if (not np.isnan(v) and v > 0.6) else "black")
        ax.set_xticks(range(len(NIVELES)), ["-" + n for n in NIVELES], rotation=45)
        ax.set_yticks(range(len(tecnicas)), tecnicas)
        ax.set_title(cc)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_matriz.pdf"))
    fig.savefig(os.path.join(FIG, "fig_matriz.png"), dpi=200)
    plt.close(fig)

    # Cifras clave
    opt = d[d.nivel != "O0"]
    for cc in compiladores:
        x = opt[(opt.compilador == cc) & (opt.tecnica == "T1")]
        nota(f"[PI1] {cc}: memset (T1) deja el secreto en {x.categoria.isin(QUEDA).sum()}/{len(x)} "
             f"configuraciones optimizadas")
    seguras = [t for t in tecnicas
               if not opt[(opt.tecnica == t) & (opt.categoria != "error")].empty
               and not opt[(opt.tecnica == t)].categoria.isin(QUEDA).any()]
    nota(f"[PI1] Técnicas protegidas en todas las configuraciones optimizadas: {', '.join(seguras)}")
    errores = d[d.categoria == "error"]
    if len(errores):
        nota(f"[PI1] Configuraciones con error de compilación: {len(errores)} "
             f"(técnicas {', '.join(sorted(errores.tecnica.unique()))})")

    # Pases responsables
    p = d[d.pase.notna() & (d.pase != "")]
    if len(p):
        t = p.groupby(["pase", "compilador"]).size().unstack(fill_value=0)
        t.index.name = "Pase"
        tabla_latex(t, "tabla_pases.tex")
        for (pase, cc), n in p.groupby(["pase", "compilador"]).size().items():
            nota(f"[Pases] {cc}: {pase} -> {n} casos")

    # Tamaño de código (PI3): P1, 64 B, -O2
    s = d[(d.nivel == "O2") & (d.patron == "P1") & (d.tamano == 64)]
    t0 = pd.read_csv(os.path.join(RESULTADOS, "matriz.csv"))
    t0 = t0[(t0.tecnica == "T0") & (t0.nivel == "O2") & (t0.patron == "P1") & (t0.tamano == 64)]
    base = dict(zip(t0.compilador, t0.bytes_victima))
    tab = s.pivot_table(index="tecnica", columns="compilador", values="bytes_victima", aggfunc="first")
    tab = tab[[c for c in compiladores if c in tab.columns]]
    tab = tab.apply(lambda col: pd.Series(
        [f"{int(v)} ({int(v) - int(base[col.name]):+d})" if v == v and v >= 0 else "n/c"
         for v in col], index=col.index))
    tab.index.name = "Técnica"
    tabla_latex(tab, "tabla_tamano.tex")


# ---------------------------------------------------------------------------
# PI2: LTO
# ---------------------------------------------------------------------------
def lto():
    ruta = os.path.join(RESULTADOS, "lto.csv")
    if not os.path.exists(ruta):
        return
    d = pd.read_csv(ruta)
    d = d[d.tecnica != "T0"]
    letra = {"protegido": "P", "vulnerable": "V", "ineficaz": "I", "no_concluyente": "N", "error": "n/c"}

    def celda(x):
        c = x.value_counts()
        if len(c) == 1:
            return letra[c.index[0]]
        return " ".join(f"{n}{letra[k]}" for k, n in c.items())

    d["col"] = d.compilador + " " + d.config
    orden = list(dict.fromkeys(d.col))
    t = d.groupby(["tecnica", "col"]).categoria.agg(celda).unstack()[orden]
    t.index.name = "Técnica"
    tabla_latex(t, "tabla_lto.tex")
    for cc in dict.fromkeys(d.compilador):
        x = d[d.compilador == cc]
        sep = x[(x.config == "separada")]
        for cfg in [c for c in dict.fromkeys(x.config) if c != "separada"]:
            y = x[x.config == cfg]
            cambian = sorted(set(sep[sep.categoria == "protegido"].tecnica)
                             & set(y[y.categoria.isin(QUEDA)].tecnica))
            nota(f"[PI2] {cc} {cfg}: técnicas protegidas por separado que dejan el secreto con LTO: "
                 f"{', '.join(cambian) or 'ninguna'}")


# ---------------------------------------------------------------------------
# PI3: costo
# ---------------------------------------------------------------------------
def costo():
    ruta = os.path.join(RESULTADOS, "costo_resumen.csv")
    if not os.path.exists(ruta):
        return
    d = pd.read_csv(ruta)
    compiladores = list(dict.fromkeys(d.compilador))
    fig, ejes = plt.subplots(1, len(compiladores), figsize=(7.0, 2.6), sharey=True)
    ejes = np.atleast_1d(ejes)
    marcadores = "o s ^ v D P X *".split()
    for ax, cc in zip(ejes, compiladores):
        x = d[d.compilador == cc]
        for k, t in enumerate(dict.fromkeys(x.tecnica)):
            y = x[x.tecnica == t].sort_values("tamano")
            ax.errorbar(y.tamano, y.mediana_ns,
                        yerr=[y.mediana_ns - y.q1, y.q3 - y.mediana_ns],
                        marker=marcadores[k % len(marcadores)], markersize=3, linewidth=1,
                        capsize=2, label="línea base" if t == "base" else t)
        ax.set_xscale("log", base=2)
        ax.set_xticks([32, 256, 4096, 65536], ["32", "256", "4 Ki", "64 Ki"])
        ax.minorticks_off()
        ax.set_yscale("log")
        ax.set_xlabel("Tamaño del búfer (bytes)")
        ax.set_title(cc)
        ax.grid(True, which="major", linewidth=0.3, alpha=0.5)
    ejes[0].set_ylabel("Tiempo por borrado (ns, mediana)")
    ejes[-1].legend(fontsize=6, ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_costo.pdf"))
    fig.savefig(os.path.join(FIG, "fig_costo.png"), dpi=200)
    plt.close(fig)
    for cc in compiladores:
        x = d[(d.compilador == cc) & (d.tamano == 4096)].set_index("tecnica").mediana_ns
        rel = ", ".join(f"{t}={x[t] / x['base']:.2f}x" for t in x.index if t != "base")
        nota(f"[PI3] {cc}, 4 KiB, costo relativo a la línea base: {rel}")


if __name__ == "__main__":
    matriz()
    lto()
    costo()
    with open(os.path.join(FIG, "resumen.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lineas_resumen) + "\n")
    print(f"\nFiguras y tablas guardadas en {FIG}")
