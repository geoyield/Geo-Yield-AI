# Investigación de zonificación PGM

Scripts usados para ampliar el corpus legal de zonificación de 3 a 10
artículos verificados, y para construir la geocodificación automática de
direcciones. No son parte de la aplicación -- son herramientas de
investigación de un momento concreto, documentadas aquí para que el
proceso sea reproducible si hace falta ampliar la cobertura más adelante.

## Orden en que se usaron

1. **`diagnostico_amb.py`** -- primer contacto con la API abierta del AMB
   (`opendata.amb.cat/api-amb/search/articles_NUMAMB`). Descarga la
   respuesta cruda y confirma la forma real de los datos (`count`,
   `items`) y los nombres reales de los campos (`titol`, `description`,
   `numeroArticle`, `titolNormativa`) -- ninguno coincidía con lo que se
   había asumido al principio.

2. **`extraer_candidatos.py`** -- una vez identificados los artículos
   candidatos (305, 306, 307, 308, 309, 313) filtrando por
   `titolNormativa == "num_pgm.titol_4"` y comparando títulos contra la
   leyenda de códigos `CLAU_URB`, extrae y limpia su texto completo para
   revisión manual.

3. **`buscar_pendientes.py`** -- trae el Artículo 304 (una referencia
   cruzada citada dentro del 306) y busca en los 574 artículos completos
   cualquier mención a "desenvolupament", para las claus 19/20b/22b que
   no tienen artículo general propio (se rigen por Plan Parcial
   específico de cada parcela, no por una norma única).

4. **`cargar_articulos_nuevos.py`** -- carga los 7 artículos verificados
   (304, 305, 306, 307, 308, 309, 313) a `legal_chunks`, con comprobación
   de duplicados. Es el único de los cinco con valor operativo real más
   allá de la investigación puntual -- se podría volver a correr si la
   base de datos se reinicia.

5. **`probar_geocodificacion.py`** -- prueba independiente de Nominatim
   (geocodificación de direcciones) antes de construir
   `backend/geo/geocoding.py`, para confirmar qué campos trae la
   respuesta real y si permiten identificar el distrito.

## Hallazgos clave que no son obvios desde el código final

- El servicio `MapServer` del AMB con sufijo `_25831` es de **solo
  caché** (no soporta consultas) -- hace falta la versión sin sufijo,
  usando la operación `identify`, no `query`.
- Las claus `19`, `20b` y `22b` no tienen un artículo general: son zonas
  de "desenvolupament" con un código de desarrollo único por parcela
  (decenas de ellos, en `num_pgm.titol_8`), no una categoría aplicable a
  toda la ciudad.
- `curl` interpreta `{ }` en una URL como expansión de múltiples
  peticiones -- hace falta `-g` para desactivarlo al llamar al `identify`
  del AMB manualmente.