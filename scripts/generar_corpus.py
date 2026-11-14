#!/usr/bin/env python3
"""Genera el corpus de programas de prueba en corpus/.

Estructura:
  corpus/arnes_P1_64.c            arnés del oráculo dinámico (uno por patrón y tamaño)
  corpus/P1_T1_64/victima.c       función bajo prueba (patrón x técnica x tamaño)
  corpus/P1_T9_64/util.c          solo T9: función de borrado en otra unidad de compilación

Uso: python3 scripts/generar_corpus.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import CORPUS, PATRONES, TECNICAS, TAMANOS, UTIL_T9, fuente_victima, fuente_arnes


def escribir(ruta, texto):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)


def main():
    total = 0
    for patron in PATRONES:
        for n in TAMANOS:
            escribir(os.path.join(CORPUS, f"arnes_{patron}_{n}.c"), fuente_arnes(patron, n))
            for tecnica in TECNICAS:
                d = os.path.join(CORPUS, f"{patron}_{tecnica}_{n}")
                escribir(os.path.join(d, "victima.c"), fuente_victima(patron, tecnica, n))
                if tecnica == "T9":
                    escribir(os.path.join(d, "util.c"), UTIL_T9)
                total += 1
    print(f"Corpus generado: {total} programas de prueba en {CORPUS}")


if __name__ == "__main__":
    main()
