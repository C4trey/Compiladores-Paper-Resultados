#!/usr/bin/env bash
# Prueba mínima de los dos oráculos con T1 (memset) en cada nivel de optimización.
#  - Oráculo estático (diferencial): si el ensamblador CON borrado es idéntico
#    al ensamblador SIN borrado, el compilador eliminó el borrado.
#  - Oráculo dinámico: ejecuta y busca el secreto en la pila.
# Uso: ./probar.sh            (usa los 4 compiladores del Dockerfile)
#      COMPILADORES="gcc-15" ./probar.sh
set -e
cd "$(dirname "$0")"
COMPILADORES="${COMPILADORES:-gcc-13 gcc-15 clang-18 clang-22}"
# Ubuntu activa _FORTIFY_SOURCE por defecto en GCC (no en Clang): se desactiva en todo.
FLAGS="-U_FORTIFY_SOURCE"
filtrar() { grep -vE '^\s*\.(file|ident|section|text|globl|type|size|p2align|cfi)' "$1"; }

for cc in $COMPILADORES; do
  $cc -O0 $FLAGS -c arnes.c -o arnes.o
  for o in O0 O1 O2 O3 Os Oz; do
    $cc -$o $FLAGS          -S victima.c -o sin.s
    $cc -$o $FLAGS -DBORRAR -S victima.c -o con.s
    $cc -$o $FLAGS -DBORRAR -c victima.c -o con.o
    $cc con.o arnes.o -o prueba
    if diff <(filtrar con.s) <(filtrar sin.s) >/dev/null; then est=ELIMINADO; else est=PRESENTE; fi
    echo "$cc -$o  estatico=$est  dinamico=$(./prueba)"
  done
done

# Control: sin borrado y con -O0 el oráculo dinámico DEBE encontrar el secreto.
cc=$(echo $COMPILADORES | cut -d' ' -f1)
$cc -O0 $FLAGS -c victima.c -o ctrl.o && $cc -O0 $FLAGS -c arnes.c -o arnes.o && $cc ctrl.o arnes.o -o ctrl
echo "control sin borrado: $(./ctrl)"
rm -f *.o *.s prueba ctrl
