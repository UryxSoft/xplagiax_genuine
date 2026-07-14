# Escalado de xPlagiaX — topologías y presupuesto de recursos

Complemento operativo de `ARCHITECTURE.md` (ADR-007/010). Describe las tres
topologías soportadas, cuándo pasar de una a otra y el presupuesto de RAM
que justifica cada decisión.

## Por qué NO Elasticsearch para este servicio

Cada nodo Elasticsearch es una JVM con 2–4 GB de heap mínimo antes de
indexar un solo documento — incompatible con el objetivo de "servicio
pluma" (NFR-03: < 0.5 GB residentes por nodo). TurboVec cuantizado + mmap
cubre decenas de millones de chunks en un solo archivo replicable; la
distribución se resuelve con réplicas stateless, no con un cluster.

## Presupuesto de RAM por proceso web

| Componente | float32 e5-large | Perfil pluma (ONNX e5-small int8) |
|---|---|---|
| Modelo de embeddings | ~2.24 GB | ~120 MB |
| Flask + deps | ~150 MB | ~150 MB |
| Índice TurboVec | RSS acotado por mmap (working set) | igual, y 384 dims ≈ 2.7× menos disco |
| **Total por worker gunicorn** | **> 2.4 GB** | **< 500 MB** |

Con `preload_app` (gunicorn.conf.py) el modelo se carga una vez en el
master y los workers lo comparten copy-on-write: N workers ≈ 1× modelo,
no N×.

## Topología 1 — single-node (default)

```
docker compose up -d
```

Un proceso web posee el índice (`INDEX_WRITE_MODE=local`), escrituras
sincrónicas, jobs inline. Sirve hasta que la CPU de un nodo se queda corta
o necesitas ingestión sin bloquear búsquedas.

## Topología 2 — multi-nodo lectura escalada (la que cubre el 99%)

```
docker compose -f docker-compose.multinode.yml up -d --scale app=3
```

```
                nginx (LB, DNS round-robin)
               /       |        \
          app x N réplicas (INDEX_WRITE_MODE=worker, índice :ro)
               \       |        /
                Redis (jobs + cache L2)   PostgreSQL (metadata)
                        |
                worker indexador (ÚNICO writer: WAL + snapshots versionados)
                        |
                volumen turbovec_data (manifest + index.vN)
```

- Las réplicas web son stateless y solo-lectura sobre el índice: escalar
  lectura = `--scale app=N`. El hot-reload por manifest hace que cada
  réplica adopte la versión nueva del índice sin reinicio.
- Toda escritura (`POST /index`, `DELETE /documents/{id}`) viaja como job
  por Redis Streams al worker. **Nunca escales el worker a más de 1** sin
  particionar antes (abajo): el diseño es single-writer por directorio de
  índice.
- Durabilidad: WAL fsync + checkpoints (`INDEX_CHECKPOINT_EVERY_OPS`);
  recuperación = snapshot del manifest + replay del WAL.
- La cache L2 en Redis comparte invalidación entre réplicas: indexar en el
  worker invalida el namespace del tenant para todos.

## Topología 3 — particionado (solo > ~50M chunks)

No implementada; plan cuando llegue la presión real:

1. Particionar por **(idioma, tema)** — partición natural: el filtro-primero
   (ADR-004) ya enruta cada búsqueda a un solo par idioma+tema, así que el
   coordinador manda cada query a UNA partición y solo hace fan-out en
   búsquedas sin filtro.
2. Un worker single-writer **por partición** (directorio de índice propio),
   mismo código de Fase 3.
3. Evitar `hash(id) % N`: destruye la localidad idioma+tema que es la
   ventaja de CPU/RAM de este diseño.

## Señales para cambiar de topología

| Señal | Acción |
|---|---|
| CPU sostenida > 70% en el nodo web | Topología 2, añadir réplicas |
| Ingestión bloquea búsquedas | Topología 2 (writer separado) |
| P95 de búsqueda degradado con réplicas ociosas | Revisar cache L2 / calentar mmap, no escalar |
| Corpus > ~50M chunks o WAL/checkpoint dominan E/S | Topología 3 (particionar) |
