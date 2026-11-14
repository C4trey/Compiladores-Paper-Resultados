#!/usr/bin/env python3
"""Experimento PI2: efecto de la optimización en tiempo de enlace (LTO).

Cada programa tiene tres unidades de compilación:
  cripto.c  -> victima(), que llama a limpiar(buf, N)
  util.c    -> limpiar(), implementada con cada técnica T1-T7 (T0 = vacía, control)
  arnes.c   -> oráculo dinámico; SIEMPRE -O0 y sin LTO
Configuraciones (todas -O2):
  GCC:   separada | lto (-flto)
  Clang: separada | lto (-flto -fuse-ld=lld) | thinlto (-flto=thin -fuse-ld=lld)
El oráculo estático compara el desensamblado del ejecutable final (victima + limpiar)
con el del control T0 en la misma configuración, porque con LTO el código se genera al enlazar.

Salida: resultados/lto.csv
"""
import csv
import os
import sys
import tempfile
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import (BASE, COMPILADORES, CORPUS, PATRONES, RESULTADOS, TAMANOS, CABECERA,
                   PATRON_CODIGO, PUNTERO, categoria, correr_binario, ejecutar, es_gcc,
                   extraer_funciones_objdump, fuente_arnes)

TECNICAS_LTO = ["T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7"]
DIR_LTO = os.path.join(CORPUS, "lto")

UTIL = """#define _GNU_SOURCE
#include <stddef.h>
#include <string.h>
{decl}
/* Función de borrado en su propia unidad de compilación ({t}). */
void limpiar(void *p, size_t n) {{
  unsigned char *b = p;
  {codigo}
}}
"""
CODIGO_UTIL = {
    "T0": "(void)b; (void)n;   /* control: no borra */",
    "T1": "memset(b, 0, n);",
    "T2": "for (size_t i = 0; i < n; i++) b[i] = 0;",
    "T3": "volatile unsigned char *vp = b;\n  for (size_t i = 0; i < n; i++) vp[i] = 0;",
    "T4": "memset_v(b, 0, n);",
    "T5": "memset(b, 0, n);\n  __asm__ __volatile__(\"\" : : \"r\"(b) : \"memory\");",
    "T6": "explicit_bzero(b, n);",
    "T7": "memset_explicit(b, 0, n);",
}
DECL_UTIL = {"T4": "static void *(*volatile memset_v)(void *, int, size_t) = memset;"}


def configuraciones(cc):
    if es_gcc(cc):
        return [("separada", [], []), ("lto", ["-flto"], ["-flto"])]
    return [("separada", [], []),
            ("lto", ["-flto"], ["-flto", "-fuse-ld=lld"]),
            ("thinlto", ["-flto=thin"], ["-flto=thin", "-fuse-ld=lld"])]


def generar():
    os.makedirs(DIR_LTO, exist_ok=True)
    for t in TECNICAS_LTO:
        with open(os.path.join(DIR_LTO, f"util_{t}.c"), "w", encoding="utf-8") as f:
            f.write(UTIL.format(decl=DECL_UTIL.get(t, ""), t=t, codigo=CODIGO_UTIL[t]))
    for p in PATRONES:
        for n in TAMANOS:
            decl = "void limpiar(void *p, size_t n);   /* definida en util.c */"
            src = CABECERA.format(n=n, decl=decl) + "\n" + PATRON_CODIGO[p].format(
                borrado=f"limpiar({PUNTERO[p]}, N);")
            with open(os.path.join(DIR_LTO, f"cripto_{p}_{n}.c"), "w", encoding="utf-8") as f:
                f.write(src)
            with open(os.path.join(DIR_LTO, f"arnes_{p}_{n}.c"), "w", encoding="utf-8") as f:
                f.write(fuente_arnes(p, n))


def construir(cc, cflags, ldflags, tecnica, patron, n, tmp):
    objs = []
    for nombre, src in [("cripto", f"cripto_{patron}_{n}.c"), ("util", f"util_{tecnica}.c")]:
        obj = os.path.join(tmp, f"{nombre}_{tecnica}.o")
        code, _, err = ejecutar([cc, "-O2", *BASE, *cflags, "-c",
                                 os.path.join(DIR_LTO, src), "-o", obj])
        if code != 0:
            return None, err
        objs.append(obj)
    arnes = os.path.join(tmp, "arnes.o")
    if not os.path.exists(arnes):
        ejecutar([cc, "-O0", *BASE, "-c", os.path.join(DIR_LTO, f"arnes_{patron}_{n}.c"),
                  "-o", arnes])
    prog = os.path.join(tmp, f"prog_{tecnica}")
    code, _, err = ejecutar([cc, "-O2", *ldflags, *objs, arnes, "-o", prog])
    return (prog, "") if code == 0 else (None, err)


def desensamblar(prog):
    _, out, _ = ejecutar(["objdump", "-d", "--no-show-raw-insn", prog])
    return extraer_funciones_objdump(out)


def evaluar(cfg):
    cc, (nombre_cfg, cflags, ldflags), tecnica, patron, n = cfg
    fila = dict(compilador=cc, config=nombre_cfg, tecnica=tecnica, patron=patron, tamano=n,
                estatico="", dinamico="", racha="", determinista="", categoria="", error="")
    with tempfile.TemporaryDirectory() as tmp:
        prog, err = construir(cc, cflags, ldflags, tecnica, patron, n, tmp)
        if prog is None:
            fila.update(estatico="NO_COMPILA", dinamico="NO_COMPILA", categoria="error",
                        error=err.strip().splitlines()[-1][:150] if err.strip() else "")
            return fila
        prog0, _ = construir(cc, cflags, ldflags, "T0", patron, n, tmp)
        fila["estatico"] = "ELIMINADO" if desensamblar(prog) == desensamblar(prog0) else "PRESENTE"
        din, racha, det = correr_binario(prog, 3)
        fila.update(dinamico=din, racha=racha, determinista="si" if det else "no",
                    categoria=categoria(tecnica, fila["estatico"], din))
    return fila


def main():
    generar()
    configs = [(cc, c, t, p, n) for cc in COMPILADORES for c in configuraciones(cc)
               for t in TECNICAS_LTO for p in PATRONES for n in TAMANOS]
    print(f"Evaluando {len(configs)} configuraciones de LTO...")
    filas = []
    with Pool() as pool:
        for i, fila in enumerate(pool.imap_unordered(evaluar, configs), 1):
            filas.append(fila)
            if i % 50 == 0 or i == len(configs):
                print(f"  {i}/{len(configs)}")
    orden = {v: i for i, v in enumerate(COMPILADORES + ["separada", "lto", "thinlto"]
                                        + TECNICAS_LTO + PATRONES)}
    filas.sort(key=lambda f: (orden[f["compilador"]], orden[f["config"]], orden[f["tecnica"]],
                              orden[f["patron"]], f["tamano"]))
    os.makedirs(RESULTADOS, exist_ok=True)
    salida = os.path.join(RESULTADOS, "lto.csv")
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"Resultados guardados en {salida}")
    ctrl = [f for f in filas if f["tecnica"] == "T0"]
    print(f"Validación: T0 (sin borrado) da RESIDUO en {sum(f['dinamico'] == 'RESIDUO' for f in ctrl)}/{len(ctrl)}")


if __name__ == "__main__":
    main()
