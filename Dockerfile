# Entorno reproducible para el estudio de DSE y borrado de memoria.
# Ubuntu 26.04 trae glibc 2.43, la primera versión con memset_explicit (C23).
FROM ubuntu:26.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc-13 gcc-15 \
        clang-18 clang-22 lld-18 lld-22 \
        libc6-dev binutils make git \
        util-linux procps \
        python3 python3-numpy python3-pandas python3-matplotlib \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
CMD ["bash"]
