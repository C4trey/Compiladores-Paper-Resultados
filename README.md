# ¿Se borran realmente los secretos?

Artefacto del artículo *"¿Se borran realmente los secretos? Evaluación de técnicas
de limpieza de memoria frente a las optimizaciones de GCC y Clang"*.

## Requisitos
- Docker (en Windows: Docker Desktop con WSL 2).
- CPU x86-64.

## Reproducir
```bash
docker build -t dse-lab .
docker run --rm -it -v "$PWD":/work dse-lab bash
# dentro del contenedor:
./scripts/entorno.sh
./prototipo/probar.sh
```

## Estructura
| Carpeta | Contenido |
|---|---|
| `prototipo/` | prueba mínima de los dos oráculos |
| `scripts/` | generación del corpus, ejecución de la matriz, LTO, benchmarks y figuras |
| `corpus/` | programas de prueba generados |
| `resultados/` | CSV con los datos crudos y descripción del entorno |
| `figuras/` | figuras del artículo, generadas por script |

## Autores
Andy Berrú Tenorio, José Rojas Cruz — Universidad de Ingeniería y Tecnología (UTEC).
