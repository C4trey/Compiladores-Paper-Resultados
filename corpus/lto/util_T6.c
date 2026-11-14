#define _GNU_SOURCE
#include <stddef.h>
#include <string.h>

/* Función de borrado en su propia unidad de compilación (T6). */
void limpiar(void *p, size_t n) {
  unsigned char *b = p;
  explicit_bzero(b, n);
}
