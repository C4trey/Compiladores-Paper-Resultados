#define _GNU_SOURCE
#include <stddef.h>
#include <string.h>

/* Función de borrado en su propia unidad de compilación (T2). */
void limpiar(void *p, size_t n) {
  unsigned char *b = p;
  for (size_t i = 0; i < n; i++) b[i] = 0;
}
