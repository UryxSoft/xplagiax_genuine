# xPlagiaX — Fase 2: Investigación SOTA (Research Report)

> Rol: investigador. Fuentes verificadas jul-2026. Cada sección termina con **Impacto en ADR** — qué decisión del `ARCHITECTURE.md` confirma, ajusta o contradice.
> **Sin código.** Este documento alimenta el rediseño (Fase 3, Opus).

---

## 1. TurboQuant / TurboVec — el paper y sus implicaciones

**Paper:** *TurboQuant: Online Vector Quantization with Near-optimal Distortion Rate* — [arXiv:2504.19874](https://arxiv.org/abs/2504.19874), aceptado en [ICLR 2026](https://iclr.cc/virtual/2026/poster/10006985) ([OpenReview](https://openreview.net/forum?id=tO3ASKZlok)).

**Hallazgos clave:**

- **Data-oblivious:** rotación aleatoria induce distribución Beta concentrada por coordenada (→ Gaussiana N(0,1/d) en alta dimensión) *independiente de los datos*. Por eso no hay fase de entrenamiento ni rebuilds — confirma la elección para indexación online/incremental.
- **Cuantizador escalar óptimo por coordenada (Lloyd-Max)** calculado analíticamente, no desde datos. Distorsión dentro de factor ~2.7× del límite inferior information-theoretic (Shannon).
- **Dos variantes:** MSE-quantizer y, encima, un 1-bit Quantized JL (QJL) sobre el residual que produce estimador de producto interno **insesgado**. La implementación turbovec añade además renormalización de longitud por vector (idea tomada de [RaBitQ, SIGMOD 2024](https://arxiv.org/abs/2405.12497)) — corrige el sesgo hacia abajo del producto interno a coste cero en búsqueda.
- **Régimen débil: baja dimensión.** La asunción Beta es asintótica; en d≈200 (GloVe) el 2-bit pierde vs 4-bit. Con e5-large (d=1024) estamos en régimen favorable, pero **2-bit es la config más arriesgada en recall**; el propio benchmark del repo muestra que FAISS gana los configs 2-bit en x86.
- La calibración **TQ+** (shift+scale por coordenada, congelada en el primer `add`) recupera hasta +1.4pp R@1 en los casos que más derivan.

**Impacto en ADR:**
- ✅ Confirma ADR-002 (IdMapIndex, online ingest, allowlist).
- ⚠️ **Ajuste recomendado:** default **4-bit**, no 2-bit. A d=1024: 4-bit = 512 B/vector → 10M chunks ≈ **5.1 GB on-disk** (vs 2.6 GB a 2-bit). El presupuesto mmap/RSS de §3.1 del ADR debe recalcularse para 4-bit; 2-bit queda como perfil "low-memory" con pérdida de recall documentada.
- ⚠️ Primer `add` fija la calibración TQ+ → el **primer lote debe ser representativo del corpus** (mezcla de idiomas/temas), no un solo documento. Añadir al pipeline de bootstrap.

---

## 2. Embeddings multilingües — ¿sigue siendo e5-large la elección?

**Panorama 2025–2026** ([MTEB v2](https://www.codesota.com/benchmarks/mteb), [comparativa 2026](https://app.ailog.fr/en/blog/news/embedding-models-2026), [reporte técnico mE5](https://arxiv.org/pdf/2402.05672)):

| Modelo | MTEB (v2 aprox.) | Dim | Local/air-gapped | Nota |
|--------|------------------|-----|------------------|------|
| Qwen3-Embedding-8B | ~70.6 | 4096 | Sí, pero 8B params — caro en CPU | Mejor calidad bruta |
| Qwen3-Embedding-0.6B | competitivo | 1024 | Sí, ligero | Mejor calidad/coste local |
| voyage-3-large / Cohere embed-v4 | 65–66 | — | ❌ API cloud | Descartados (air-gapped) |
| **BGE-M3** | ~63; 100+ idiomas (Q1 2026) | 1024 | ✅ | Denso + sparse + ColBERT multi-vector en un modelo |
| **multilingual-e5-large** | ~61–62 | 1024 | ✅ | Baseline sólido, maduro, barato |

**Hallazgo relevante para plagio:** BGE-M3 emite **tres representaciones** (dense/sparse/multi-vector) de una pasada. La señal *sparse* (léxica) es útil como término extra del score compuesto (coincidencia casi-exacta con reordenamiento de palabras) sin segundo modelo.

**Impacto en ADR:**
- ✅ Confirma ADR-003 (interfaz intercambiable — imprescindible, el ranking cambia cada trimestre).
- 🔄 **Recomendación:** default `multilingual-e5-large` se mantiene (maduro, d=1024, requisito del prompt), pero **BGE-M3 como perfil alternativo de primera clase** en la config, y benchmark interno A/B sobre corpus académico ES/EN antes de congelar. Ambos d=1024 → mismo footprint TurboVec, swap sin migración de índice *si* se reindexan los vectores.

---

## 3. Detección de plagio semántico — estado del arte

**Fuentes:** [PAN 2025 Plagiarism Detection Task](https://arxiv.org/pdf/2510.06805), [revisión sistemática multilingüe 2025](https://thesai.org/Downloads/Volume16No8/Paper_36-A_Systematic_Review_of_Multilingual_Plagiarism_Detection.pdf), [estudio árabe/inglés long-docs](https://pmc.ncbi.nlm.nih.gov/articles/PMC12453725/).

**Hallazgos:**

1. **El campo se movió a "generative plagiarism"**: PAN 2025 incluye texto parafraseado por LLM como adversario principal. Los sistemas ganadores alinean fragmentos por similitud semántica densa (se cita rendimiento fuerte de modelos tipo Linq-Embed-Mistral) + etapa de **text alignment** fina para localizar spans exactos.
2. **Arquitectura ganadora = 2 etapas**: (a) *source retrieval* — recuperar documentos candidatos con embeddings/BM25; (b) *text alignment* — alinear pares de fragmentos y fusionar spans contiguos. Nuestro pipeline (Top-K por segmento → agrupación → fusión por documento) es exactamente esta forma. ✅
3. **Cross-lingual:** los enfoques con espacio multilingüe compartido (mismo embedding para ES/EN) superan a los de capa de traducción. Detectar plagio ES↔EN "gratis" con e5/BGE-M3 es viable y debe ser modo soportado, no mejora futura.
4. **Métrica:** PAN usa PlagDet (precision/recall/granularidad a nivel de *caracteres del span*). Reportar solo % por documento es insuficiente para uso académico serio — el evaluador quiere ver **qué span** coincide con **qué fuente**.

**Impacto en ADR:**
- ✅ Pipeline de 2 etapas confirmado.
- 🔄 **Ajuste:** elevar "detección translingüe" de §20 (futuro) a **requisito funcional** (RF nuevo): modo `cross-lingual` que omite el filtro de idioma y compara en el espacio multilingüe compartido. El filtro idioma-primero (ADR-004) pasa a ser *default configurable*, no invariante — con nota: en modo cross-lingual el componente `language_match` del score se re-normaliza fuera.
- 🔄 **Ajuste respuesta API:** `chunk_mas_parecido` ya devuelve span; añadir **todos los pares alineados** (span consulta ↔ span fuente) para granularidad tipo PlagDet.

---

## 4. Chunking — evidencia contra el dogma "semántico siempre gana"

**Fuentes:** [evaluación NAACL 2025 Findings / coste-efectividad](https://arxiv.org/html/2606.00881v1), [guía 2026](https://www.firecrawl.dev/blog/best-chunking-strategies-rag), [Mix-of-Granularity](https://arxiv.org/pdf/2406.00456).

**Hallazgos:**

- Chunks fijos de ~200 palabras **igualan o superan** al chunking semántico en la mayoría de benchmarks generales, a fracción del coste (el chunking semántico requiere un embedding por oración → 200–300 embeddings extra por documento de 10k palabras).
- Pero en dominios con estructura fuerte (clínico/legal), el chunking alineado a límites lógicos gana por mucho (87% vs 13% en un estudio clínico). Documentos académicos (secciones, párrafos) están en el medio.
- Mejores recalls reportados: LLM/Cluster semantic chunkers ~0.91–0.92 vs recursive splitter ~0.85–0.90 — ganancia real pero modesta.

**Impacto en ADR:**
- ✅ Nuestra estrategia híbrida (párrafo → oración → tope de tokens, overlap 20%) es la zona dulce coste/beneficio: respeta límites lógicos del Markdown (estructura académica) **sin** pagar embeddings por oración.
- ⚠️ **"Adaptive/semantic chunking" se mantiene en mejoras futuras, con evidencia en contra de priorizarlo.** No prometerlo como ganancia segura. Benchmark interno antes de invertir.
- 🔄 Overlap 20% + fusión de spans en alignment: cuidar deduplicación de matches solapados en el agregador (dos chunks solapados matcheando la misma fuente no son dos evidencias).

---

## 5. Fingerprinting: MinHash vs SimHash

**Fuentes:** [In Defense of MinHash Over SimHash](https://arxiv.org/pdf/1407.4416), [guía práctica datasketch/LSH](https://yorko.github.io/2023/practical-near-dup-detection/), [resumen técnicas dedup LLM-scale](https://apxml.com/courses/how-to-build-a-large-language-model/chapter-7-data-cleaning-preprocessing-pipelines/near-duplicate-exact-duplicate-detection).

**Hallazgos:**

- Teoría y práctica favorecen **MinHash para estimar Jaccard entre conjuntos** (chunks, shingles de n-grams) y **SimHash (64-bit) para huella compacta de documento completo** — 64 bits de SimHash rinden como ~24 bytes de MinHash. Nuestra asignación (SimHash=doc, MinHash=chunk) coincide con la práctica. ✅
- Escala: MinHash **LSH** (bandas) da búsqueda de candidatos sublineal — imprescindible a 10M chunks; comparación lineal de firmas no escala. `num_perm` ≈ 128 es el equilibrio estándar precisión/velocidad; bandas ajustan recall/precision del filtro.
- Implementación de referencia en Python: `datasketch` (MinHash, MinHashLSH, persistencia en Redis soportada nativamente — encaja con nuestro stack).

**Impacto en ADR:**
- ✅ Cascada dedup confirmada.
- 🔄 **Precisión de diseño:** el `FingerprintRepository` debe ser **MinHashLSH sobre Redis** (no scan lineal), num_perm=128, umbral Jaccard configurable (~0.8 dedup, ~0.5 como señal de score). Shingling: 5-gramas de palabras para chunks.

---

## 6. Metadatos académicos: GROBID

**Fuentes:** [GROBID docs](https://grobid.readthedocs.io/en/latest/Introduction/), [repo](https://github.com/grobidOrg/grobid), [benchmark Meuschke et al. 2023](https://gipplab.uni-goettingen.de/wp-content/papercite-data/pdf/meuschke2023.pdf).

**Hallazgos:**

- GROBID = mejor herramienta medida para metadatos de PDFs académicos: **F1 0.958 autores, 0.935 abstract**, ~0.87 referencias; 68 etiquetas incluyendo afiliación estructurada; 2–5 s/página.
- **Debilidad exactamente donde más lo necesitamos:** afiliaciones/universidades — formatos inconsistentes producen afiliaciones duplicadas, mal estructuradas o ausentes. Es la fuente del campo `universidad`, central en nuestra respuesta.
- Tesis latinoamericanas (portadas no estándar, sin formato de paper) son distribución distinta del entrenamiento de GROBID → esperar degradación adicional.

**Impacto en ADR:**
- ✅ GROBID + MarkItDown (ADR-012) sigue siendo lo correcto.
- 🔄 **Ajuste obligado:** capa de **normalización de instituciones** post-GROBID: diccionario/gazetteer de universidades (p. ej. lista ROR — Research Organization Registry, open data, usable offline) + fuzzy matching para canonicalizar "Univ. Nacional" / "UNIVERSIDAD NACIONAL" / "U.N." al mismo registro. Sin esto, `entity_match` del score compuesto y el filtro por universidad son ruido.
- 🔄 Fallback explícito: si GROBID no da universidad, extraer de la primera página vía patrón sobre el Markdown (las tesis casi siempre la nombran en portada). `null` solo si ambos fallan.

---

## 7. Reducción de RAM — validación del enfoque mmap

Sin fuentes nuevas más allá del repo turbovec y práctica estándar; síntesis:

- mmap + índice inmutable versionado es la técnica estándar (LanceDB, DiskANN, Vespa la usan) para servir índices mayores que la RAM. ✅ ADR-007 sólido.
- **Corrección numérica derivada de §1:** con default 4-bit el fichero pasa a ~5.1 GB para 10M chunks d=1024. El RSS objetivo (<0.5 GB) sigue siendo alcanzable — el working set depende del allowlist (partición idioma+tema toca fracción pequeña de páginas), no del tamaño total. La partición filtro-primero es *también* la estrategia de localidad de páginas: **ordenar el índice físicamente por (idioma, tema)** para que las páginas calientes de una consulta sean contiguas. Añadir esta decisión al ADR (afecta a cómo asignamos rangos de ChunkId).

---

## 8. Síntesis — cambios que Fase 3 (rediseño, Opus) debe incorporar

| # | Cambio | Origen | Severidad |
|---|--------|--------|-----------|
| 1 | Default bit_width **4-bit**; 2-bit = perfil low-memory documentado | §1 | Alta (recall) |
| 2 | Bootstrap de calibración TQ+: primer `add` con lote representativo multi-idioma | §1 | Media |
| 3 | BGE-M3 perfil alternativo de primera clase; A/B interno antes de congelar modelo | §2 | Media |
| 4 | Modo **cross-lingual** como RF (no mejora futura); filtro idioma configurable | §3 | Alta (producto) |
| 5 | Respuesta con **pares de spans alineados** (granularidad PlagDet) | §3 | Alta (producto) |
| 6 | Chunking semántico/adaptativo degradado a "solo con benchmark que lo justifique" | §4 | Baja |
| 7 | Dedup de matches solapados (overlap 20%) en el agregador | §4 | Media |
| 8 | FingerprintRepository = MinHashLSH/Redis, num_perm=128, 5-gram shingles | §5 | Media |
| 9 | Normalización de universidades vía gazetteer ROR + fuzzy matching; fallback portada | §6 | Alta (calidad metadata) |
| 10 | Layout físico del índice ordenado por (idioma, tema) → localidad de páginas mmap | §7 | Media (NFR RAM) |

---

## Fuentes

- [TurboQuant — arXiv:2504.19874](https://arxiv.org/abs/2504.19874) · [ICLR 2026 poster](https://iclr.cc/virtual/2026/poster/10006985) · [OpenReview](https://openreview.net/forum?id=tO3ASKZlok)
- [RaBitQ (SIGMOD 2024)](https://arxiv.org/abs/2405.12497)
- [Multilingual E5 — technical report](https://arxiv.org/pdf/2402.05672) · [MTEB v2 leaderboard (CodeSOTA)](https://www.codesota.com/benchmarks/mteb) · [Embedding models 2026 (Ailog)](https://app.ailog.fr/en/blog/news/embedding-models-2026)
- [PAN 2025 Plagiarism Detection Task](https://arxiv.org/pdf/2510.06805) · [Systematic Review of Multilingual Plagiarism Detection (2025)](https://thesai.org/Downloads/Volume16No8/Paper_36-A_Systematic_Review_of_Multilingual_Plagiarism_Detection.pdf) · [Cross-lingual long-document study (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12453725/)
- [Chunking cost-effectiveness evaluation](https://arxiv.org/html/2606.00881v1) · [Best chunking strategies 2026 (Firecrawl)](https://www.firecrawl.dev/blog/best-chunking-strategies-rag) · [Mix-of-Granularity](https://arxiv.org/pdf/2406.00456)
- [In Defense of MinHash Over SimHash](https://arxiv.org/pdf/1407.4416) · [Practical near-dup detection with datasketch](https://yorko.github.io/2023/practical-near-dup-detection/) · [Dedup at LLM scale (ApX)](https://apxml.com/courses/how-to-build-a-large-language-model/chapter-7-data-cleaning-preprocessing-pipelines/near-duplicate-exact-duplicate-detection)
- [GROBID docs](https://grobid.readthedocs.io/en/latest/Introduction/) · [GROBID repo](https://github.com/grobidOrg/grobid) · [Benchmark of PDF extraction tools (Meuschke et al.)](https://gipplab.uni-goettingen.de/wp-content/papercite-data/pdf/meuschke2023.pdf)

---

*Fin Fase 2 (investigación). Siguiente: Fase 3 — rediseño de arquitectura (Opus) incorporando los 10 cambios de §8.*
