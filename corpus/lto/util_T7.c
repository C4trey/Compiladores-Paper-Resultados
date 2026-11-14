#define _GNU_SOURCE
#include <stddef.h>
#include <string.h>

/* Función de borrado en su propia unidad de compilación (T7). */
void limpiar(void *p, size_t n) {
  unsigned char *b = p;
  memset_explicit(b, 0, n);
}
