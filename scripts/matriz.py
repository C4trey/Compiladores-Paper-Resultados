#!/usr/bin/env python3
"""Experimento PI1: matriz de compiladores x niveles x técnicas x patrones x tamaños.

Para cada configuración:
  1. Oráculo estático diferencial: compara el ensamblador de victima() con el del
     control T0 compilado con las mismas opciones.
  2. Oráculo dinámico: enlaza con el arnés (-O0) y busca el secreto en memoria (3 ejecuciones).
  3. Tamaño en bytes de victima() (para PI3).
  4. Si el borrado fue eliminado: identifica el pase responsable.
       GCC   -> volcados -fdump-tree-dse-details y prueba con -fno-dse / -fno-tree-dse.
       Clang -> búsqueda binaria con -mllvm -opt-bisect-limit=N.

Salida: resultados/matriz.csv
Uso:    python3 scripts/matriz.py            (todos los compiladores)
        COMPILADORES="gcc-15" python3 scripts/matriz.py
"""
import csv
import glob
import os
import re
import sys
import tempfile
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import (BASE, COMPILADORES, CORPUS, EXTRA, NIVELES, PATRONES, RESULTADOS,
                   TAMANOS, TECNICAS, categoria, correr_binario, ejecutar, es_gcc,
                   extraer_funcion_asm)

CAMPOS = ["compilador", "nivel", "tecnica", "patron", "tamano", "estatico", "dinamico",
          "racha", "determinista", "categoria", "bytes_victima", "pase", "error"]


def opciones(nivel, tecnica):
    return [f"-{nivel}"] + BASE + EXTRA.get(tecnica, [])


def asm_victima(cc, nivel, tecnica, patron, n, tmp, flags_extra=()):
    src = os.path.join(CORPUS, f"{patron}_{tecnica}_{n}", "victima.c")
    out = os.path.join(tmp, f"{tecnica}.s")
    code, _, err = ejecutar([cc, *opciones(nivel, tecnica), *flags_extra, "-S", src, "-o", out])
    if code != 0:
        return None, err
    with open(out, encoding="utf-8") as f:
        return extraer_funcion_asm(f.read()), ""


def construir(cc, nivel, tecnica, patron, n, tmp, flags_extra=(), nombre="prog"):
    """Compila victima (+ util para T9) con las opciones evaluadas y enlaza con el arnés."""
    d = os.path.join(CORPUS, f"{patron}_{tecnica}_{n}")
    objs = []
    for fuente in ["victima.c"] + (["util.c"] if tecnica == "T9" else []):
        obj = os.path.join(tmp, f"{nombre}_{fuente}.o")
        code, _, err = ejecutar([cc, *opciones(nivel, tecnica), *flags_extra, "-c",
                                 os.path.join(d, fuente), "-o", obj])
        if code != 0:
            return None, None, err
        objs.append(obj)
    arnes = os.path.join(tmp, "arnes.o")
    if not os.path.exists(arnes):
        code, _, err = ejecutar([cc, "-O0", *BASE, "-c",
                                 os.path.join(CORPUS, f"arnes_{patron}_{n}.c"), "-o", arnes])
        if code != 0:
            return None, None, err
    prog = os.path.join(tmp, nombre)
    code, _, err = ejecutar([cc, *objs, arnes, "-o", prog])
    return (prog, objs[0], "") if code == 0 else (None, None, err)


def bytes_funcion(obj, nombre="victima"):
    code, out, _ = ejecutar(["nm", "-S", obj])
    for linea in out.splitlines():
        partes = linea.split()
        if len(partes) == 4 and partes[3] == nombre:
            return int(partes[1], 16)
    return -1


# ---------------------------------------------------------------------------
# Atribución del pase responsable
# ---------------------------------------------------------------------------
def pase_gcc(cc, nivel, tecnica, patron, n, tmp):
    """Busca en los volcados de GCC el primer pase que borra las escrituras a cero.
    Se revisan la DSE y la eliminación de código muerto (dce y cddce), porque en GCC
    un bucle de borrado puede eliminarse como código muerto y no como almacenamiento muerto."""
    src = os.path.join(CORPUS, f"{patron}_{tecnica}_{n}", "victima.c")
    dump = os.path.join(tmp, "dump")
    os.makedirs(dump, exist_ok=True)
    ejecutar([cc, *opciones(nivel, tecnica), "-c", src, "-o", os.path.join(dump, "v.o"),
              "-fdump-tree-dse-details", "-fdump-tree-dce-details",
              "-fdump-tree-cddce-details"], cwd=dump)
    archivos = []
    for a in glob.glob(os.path.join(dump, "*t.*")):
        m = re.search(r"\.(\d+)t\.(\w+)$", a)
        if m:
            archivos.append((int(m.group(1)), m.group(2), a))
    for _, nombre, a in sorted(archivos):          # en orden de ejecución
        with open(a, encoding="utf-8", errors="ignore") as f:
            texto = f.read()
        if nombre.startswith("dse") and re.search(r"deleted dead", texto, re.IGNORECASE):
            return "tree-" + nombre                 # p. ej. tree-dse1
        if "dce" in nombre and re.search(r"^Deleting : .*(= 0;|memset)", texto, re.MULTILINE):
            return "tree-" + nombre                 # p. ej. tree-cddce1
    # Sin rastro en los volcados de árboles: ¿lo elimina la DSE sobre RTL?
    prog, _, _ = construir(cc, nivel, tecnica, patron, n, tmp, ["-fno-dse"], "nodse")
    if prog and correr_binario(prog, 1)[0] == "LIMPIO":
        return "rtl-dse"
    return "otro"


def pase_clang(cc, nivel, tecnica, patron, n, tmp):
    """Búsqueda binaria del primer pase tras el cual el secreto queda en memoria."""
    src = os.path.join(CORPUS, f"{patron}_{tecnica}_{n}", "victima.c")
    _, _, err = ejecutar([cc, *opciones(nivel, tecnica), "-c", src, "-o",
                          os.path.join(tmp, "b.o"), "-mllvm", "-opt-bisect-limit=-1"])
    pases = {int(m.group(1)): m.group(2).strip()
             for m in re.finditer(r"BISECT: running pass \((\d+)\) (.*)", err)}
    if not pases:
        return "desconocido"

    def residuo(limite):
        prog, _, _ = construir(cc, nivel, tecnica, patron, n, tmp,
                               ["-mllvm", f"-opt-bisect-limit={limite}"], f"bis{limite}")
        return prog is not None and correr_binario(prog, 1)[0] == "RESIDUO"

    lo, hi = 0, max(pases)
    if residuo(lo) or not residuo(hi):
        return "desconocido"
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if residuo(mid):
            hi = mid
        else:
            lo = mid
    nombre = pases.get(hi, "?")
    return re.sub(r"\s+on\s+.*$", "", nombre)     # quita "on victima", "on [module]", etc.


# ---------------------------------------------------------------------------
def evaluar(cfg):
    cc, nivel, tecnica, patron, n = cfg
    fila = dict(compilador=cc, nivel=nivel, tecnica=tecnica, patron=patron, tamano=n,
                estatico="", dinamico="", racha="", determinista="", categoria="",
                bytes_victima="", pase="", error="")
    with tempfile.TemporaryDirectory() as tmp:
        asm_t, err = asm_victima(cc, nivel, tecnica, patron, n, tmp)
        if asm_t is None:
            fila.update(estatico="NO_COMPILA", dinamico="NO_COMPILA", categoria="error",
                        error=err.strip().splitlines()[-1][:150] if err.strip() else "")
            return fila
        asm_0, _ = asm_victima(cc, nivel, "T0", patron, n, tmp, EXTRA.get(tecnica, []))
        fila["estatico"] = "ELIMINADO" if asm_t == asm_0 else "PRESENTE"

        prog, obj, err = construir(cc, nivel, tecnica, patron, n, tmp)
        if prog is None:
            fila.update(dinamico="ERROR", categoria="error", error=err.strip()[-150:])
            return fila
        din, racha, det = correr_binario(prog, 3)
        fila.update(dinamico=din, racha=racha, determinista="si" if det else "no",
                    bytes_victima=bytes_funcion(obj))
        fila["categoria"] = categoria(tecnica, fila["estatico"], din)

        # Atribución: siempre que el secreto quede en memoria con optimizaciones activas.
        if fila["categoria"] in ("vulnerable", "ineficaz") and nivel != "O0":
            fila["pase"] = (pase_gcc if es_gcc(cc) else pase_clang)(cc, nivel, tecnica, patron, n, tmp)
    return fila


def main():
    if not os.path.isdir(CORPUS) or not glob.glob(os.path.join(CORPUS, "P1_T0_*")):
        sys.exit("Primero genera el corpus: python3 scripts/generar_corpus.py")
    configs = [(cc, nv, t, p, n) for cc in COMPILADORES for nv in NIVELES
               for t in TECNICAS for p in PATRONES for n in TAMANOS]
    print(f"Evaluando {len(configs)} configuraciones con {len(COMPILADORES)} compiladores...")
    os.makedirs(RESULTADOS, exist_ok=True)
    salida = os.path.join(RESULTADOS, "matriz.csv")
    filas = []
    with Pool() as pool:
        for i, fila in enumerate(pool.imap_unordered(evaluar, configs), 1):
            filas.append(fila)
            if i % 50 == 0 or i == len(configs):
                print(f"  {i}/{len(configs)}")
    orden = {v: i for i, v in enumerate(COMPILADORES + NIVELES + TECNICAS + PATRONES)}
    filas.sort(key=lambda f: (orden[f["compilador"]], orden[f["tecnica"]], orden[f["patron"]],
                              f["tamano"], orden[f["nivel"]]))
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)
    print(f"Resultados guardados en {salida}")

    # Validación de los oráculos (Sección 4.4 del artículo)
    def todas(cond):
        return all(cond(f) for f in filas)
    t0 = [f for f in filas if f["tecnica"] == "T0" and f["nivel"] == "O0"]
    t1 = [f for f in filas if f["tecnica"] == "T1" and f["nivel"] == "O0"]
    print("\nValidación de los oráculos:")
    print(f"  T0 con -O0 da RESIDUO (sensibilidad): {sum(f['dinamico'] == 'RESIDUO' for f in t0)}/{len(t0)}")
    print(f"  T1 con -O0 da LIMPIO  (especificidad): {sum(f['dinamico'] == 'LIMPIO' for f in t1)}/{len(t1)}")
    det = [f for f in filas if f["determinista"]]
    print(f"  Resultados deterministas (3 ejecuciones): {sum(f['determinista'] == 'si' for f in det)}/{len(det)}")
    errores = [f for f in filas if f["categoria"] == "error"]
    if errores:
        print(f"  Configuraciones con error: {len(errores)} (ver columna 'error' del CSV)")


if __name__ == "__main__":
    main()
