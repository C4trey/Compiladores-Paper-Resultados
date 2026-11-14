#define _GNU_SOURCE
#include <stddef.h>
#include <string.h>

/* Función de borrado en su propia unidad de compilación (T0). */
void limpiar(void *p, size_t n) {
  unsigned char *b = p;
  (void)b; (void)n;   /* control: no borra */
}
