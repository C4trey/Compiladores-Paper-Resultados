#define _GNU_SOURCE
#include <stddef.h>
#include <string.h>

/* Función de borrado en su propia unidad de compilación (T1). */
void limpiar(void *p, size_t n) {
  unsigned char *b = p;
  memset(b, 0, n);
}
