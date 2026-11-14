#define _GNU_SOURCE
#include <stddef.h>
#include <string.h>
static void *(*volatile memset_v)(void *, int, size_t) = memset;
/* Función de borrado en su propia unidad de compilación (T4). */
void limpiar(void *p, size_t n) {
  unsigned char *b = p;
  memset_v(b, 0, n);
}
