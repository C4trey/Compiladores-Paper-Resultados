#!/usr/bin/env bash
# Ejecuta todos los experimentos en orden y genera las figuras y tablas del artículo.
# Uso (dentro del contenedor): ./scripts/ejecutar_todo.sh
set -e
cd "$(dirname "$0")/.."
./scripts/entorno.sh > /dev/null
python3 scripts/generar_corpus.py
python3 scripts/matriz.py        # PI1
python3 scripts/lto.py           # PI2
python3 scripts/costo.py         # PI3 (cierra otras aplicaciones mientras corre)
python3 scripts/figuras.py
