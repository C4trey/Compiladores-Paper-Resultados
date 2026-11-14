#!/usr/bin/env python3
"""Experimento PI3: costo en tiempo de las técnicas de borrado.

Mide cuántos nanosegundos tarda una operación de borrado para tamaños de 32 B a 64 KiB.
  - Línea base: memset sobre un búfer global (el compilador no puede eliminarlo).
  - Cada medición cronometra K borrados (K se calibra para que dure >= 10 ms).
  - 30 repeticiones por configuración; el proceso se fija a un núcleo con taskset.
Resumen: mediana, rango intercuartílico (IQR) e IC del 95 % de la mediana por bootstrap
(10 000 remuestreos).

Salidas: resultados/costo_crudo.csv y resultados/costo_resumen.csv
Uso:     python3 scripts/costo.py
         COSTO_COMPILADORES="gcc-15" python3 scripts/costo.py
"""
import csv
import io
import os
import shutil
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import BASE, RESULTADOS, ejecutar

COMPILADORES = os.environ.get("COSTO_COMPILADORES", "gcc-15 clang-22").split()
NUCLEO = os.environ.get("NUCLEO", "2")
TAMANOS = [32, 256, 4096, 65536]
REPETICIONES = 30
TECNICAS = ["base", "T3", "T4", "T5", "T6", "T7", "T8", "T9"]

TECNICAS_C = r"""#define _GNU_SOURCE
#include <stddef.h>
#include <string.h>

unsigned char gbuf[65536];
static void *(*volatile memset_v)(void *, int, size_t) = memset;
void limpiar(void *p, size_t n);

/* Línea base: memset sobre un búfer global, que el compilador no puede eliminar. */
__attribute__((noinline)) void f_base(unsigned char *b, size_t n) { (void)b; memset(gbuf, 0, n); }
__attribute__((noinline)) void f_T3(unsigned char *b, size_t n) {
  volatile unsigned char *vp = b; for (size_t i = 0; i < n; i++) vp[i] = 0; }
__attribute__((noinline)) void f_T4(unsigned char *b, size_t n) { memset_v(b, 0, n); }
__attribute__((noinline)) void f_T5(unsigned char *b, size_t n) {
  memset(b, 0, n); __asm__ __volatile__("" : : "r"(b) : "memory"); }
__attribute__((noinline)) void f_T6(unsigned char *b, size_t n) { explicit_bzero(b, n); }
__attribute__((noinline)) void f_T7(unsigned char *b, size_t n) { memset_explicit(b, 0, n); }
__attribute__((noinline)) void f_T9(unsigned char *b, size_t n) { limpiar(b, n); }
"""

T8_C = r"""#include <stddef.h>
#include <string.h>
/* Se compila con -fno-builtin-memset. */
__attribute__((noinline)) void f_T8(unsigned char *b, size_t n) { memset(b, 0, n); }
"""

UTIL_C = r"""#include <stddef.h>
#include <string.h>
void limpiar(void *p, size_t n) { memset(p, 0, n); }
"""

MAIN_C = r"""#include <stdio.h>
#include <string.h>
#include <time.h>

typedef void (*borrado_t)(unsigned char *, size_t);
void f_base(unsigned char *, size_t); void f_T3(unsigned char *, size_t);
void f_T4(unsigned char *, size_t);   void f_T5(unsigned char *, size_t);
void f_T6(unsigned char *, size_t);   void f_T7(unsigned char *, size_t);
void f_T8(unsigned char *, size_t);   void f_T9(unsigned char *, size_t);

static const char *nombres[] = {"base", "T3", "T4", "T5", "T6", "T7", "T8", "T9"};
static borrado_t funciones[] = {f_base, f_T3, f_T4, f_T5, f_T6, f_T7, f_T8, f_T9};
static const size_t tamanos[] = {32, 256, 4096, 65536};
static unsigned char buf[65536];

static double ahora(void) {
  struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
  return t.tv_sec + t.tv_nsec * 1e-9;
}

static double cronometrar(borrado_t f, size_t n, long k) {
  double t0 = ahora();
  for (long i = 0; i < k; i++) f(buf, n);
  return ahora() - t0;
}

int main(void) {
  memset(buf, 0xA5, sizeof buf);
  printf("tecnica,tamano,repeticion,ns_por_op\n");
  for (int t = 0; t < 8; t++)
    for (int s = 0; s < 4; s++) {
      size_t n = tamanos[s];
      long k = 1;
      while (cronometrar(funciones[t], n, k) < 0.010) k *= 2;   /* calibración: >= 10 ms */
      for (int r = 0; r < REPS; r++)
        printf("%s,%zu,%d,%.3f\n", nombres[t], n, r, cronometrar(funciones[t], n, k) / k * 1e9);
    }
  return 0;
}
"""


def bootstrap_mediana(x, b=10000, semilla=0):
    rng = np.random.default_rng(semilla)
    medianas = np.median(rng.choice(x, size=(b, len(x)), replace=True), axis=1)
    return np.percentile(medianas, 2.5), np.percentile(medianas, 97.5)


def main():
    os.makedirs(RESULTADOS, exist_ok=True)
    crudo, resumen = [], []
    usar_taskset = shutil.which("taskset") is not None
    for cc in COMPILADORES:
        with tempfile.TemporaryDirectory() as tmp:
            for nombre, texto in [("tecnicas.c", TECNICAS_C), ("t8.c", T8_C),
                                  ("util.c", UTIL_C), ("main.c", MAIN_C)]:
                with open(os.path.join(tmp, nombre), "w") as f:
                    f.write(texto)
            objs = []
            for src, extra in [("tecnicas.c", []), ("t8.c", ["-fno-builtin-memset"]),
                               ("util.c", []), ("main.c", [f"-DREPS={REPETICIONES}"])]:
                obj = os.path.join(tmp, src + ".o")
                code, _, err = ejecutar([cc, "-O2", *BASE, *extra, "-c",
                                         os.path.join(tmp, src), "-o", obj])
                if code != 0:
                    sys.exit(f"Error compilando {src} con {cc}:\n{err}")
                objs.append(obj)
            prog = os.path.join(tmp, "bench")
            ejecutar([cc, *objs, "-o", prog])
            cmd = (["taskset", "-c", NUCLEO] if usar_taskset else []) + [prog]
            print(f"Midiendo con {cc} (núcleo {NUCLEO if usar_taskset else 'libre'})...")
            code, out, err = ejecutar(cmd, timeout=1800)
            if code != 0:
                sys.exit(f"Error ejecutando el benchmark:\n{err}")
        for fila in csv.DictReader(io.StringIO(out)):
            fila["compilador"] = cc
            crudo.append(fila)
        for t in TECNICAS:
            for n in TAMANOS:
                x = np.array([float(f["ns_por_op"]) for f in crudo if f["compilador"] == cc
                              and f["tecnica"] == t and int(f["tamano"]) == n])
                q1, med, q3 = np.percentile(x, [25, 50, 75])
                ic_inf, ic_sup = bootstrap_mediana(x)
                resumen.append(dict(compilador=cc, tecnica=t, tamano=n, mediana_ns=round(med, 3),
                                    q1=round(q1, 3), q3=round(q3, 3), iqr=round(q3 - q1, 3),
                                    ic95_inf=round(ic_inf, 3), ic95_sup=round(ic_sup, 3), n=len(x)))
    with open(os.path.join(RESULTADOS, "costo_crudo.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["compilador", "tecnica", "tamano", "repeticion", "ns_por_op"])
        w.writeheader()
        w.writerows(crudo)
    with open(os.path.join(RESULTADOS, "costo_resumen.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(resumen[0].keys()))
        w.writeheader()
        w.writerows(resumen)
    print("Resultados guardados en resultados/costo_crudo.csv y resultados/costo_resumen.csv")


if __name__ == "__main__":
    main()
