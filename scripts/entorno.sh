#!/usr/bin/env bash
# Guarda la descripción del entorno experimental (va a la tabla de Metodología).
cd "$(dirname "$0")/.."
{
  echo "== Fecha";      date -u
  echo "== CPU";        lscpu | grep -E "Model name|^CPU\(s\)|Thread\(s\) per core|Core\(s\) per socket"
  echo "== RAM";        free -h | head -2
  echo "== Kernel";     uname -r
  echo "== SO";         grep PRETTY_NAME /etc/os-release
  echo "== glibc";      ldd --version | head -1
  for c in gcc-13 gcc-15 clang-18 clang-22; do echo "== $c"; $c --version | head -1; done
  echo "== lld";        ld.lld-22 --version
  echo "== binutils";   ld --version | head -1
} > resultados/entorno.txt
cat resultados/entorno.txt
