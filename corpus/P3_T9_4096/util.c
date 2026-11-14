#include <string.h>
#include <stddef.h>

/* T9: función de borrado definida en otra unidad de compilación. */
void limpiar(void *p, size_t n) { memset(p, 0, n); }
