#define _GNU_SOURCE
#include <stddef.h>
#include <string.h>

/* Función de borrado en su propia unidad de compilación (T3). */
void limpiar(void *p, size_t n) {
  unsigned char *b = p;
  volatile unsigned char *vp = b;
  for (size_t i = 0; i < n; i++) vp[i] = 0;
}
