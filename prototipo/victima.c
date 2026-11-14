/* Función bajo prueba: maneja un secreto en un búfer local y lo borra.
 * Se compila con los flags que se quieren evaluar (-O0, -O2, -flto...). */
#include <string.h>
#include <stddef.h>

extern volatile unsigned char fuente[64]; /* el secreto viene de fuera: el compilador no puede precalcularlo */
extern volatile int sumidero;             /* el resultado se "usa": la función no se elimina entera */

__attribute__((noinline)) void victima(void) {
  unsigned char buf[64];
  for (size_t i = 0; i < sizeof buf; i++) buf[i] = fuente[i];
  int s = 0;
  for (size_t i = 0; i < sizeof buf; i++) s += buf[i];
  sumidero = s;
#ifdef BORRAR
  memset(buf, 0, sizeof buf);   /* T1: la técnica que se evalúa */
#endif
}
