# Investigación de Zonificación PGM (Diario de Laboratorio)

Esta carpeta contiene los scripts utilizados para investigar, mapear y ampliar el corpus legal del *Pla General Metropolità (PGM)*, pasando de 3 a 10 zonas urbanísticas verificadas. También incluye las pruebas tempranas para la geocodificación automática de direcciones. 

**Nota Arquitectónica:** Estos scripts **no forman parte de la aplicación principal (Backend)**. Son herramientas de investigación de un momento concreto (*One-off scripts*). Se documentan aquí para garantizar que el proceso sea reproducible si en el futuro fuera necesario ampliar la cobertura a más zonas de Barcelona.

---

## Orden de Ejecución de la Investigación

El proceso de descubrimiento de datos se realizó en el siguiente orden:

1. **`diagnostico_amb.py`**
   - **Propósito:** Primer contacto exploratorio con la API abierta del Área Metropolitana de Barcelona (AMB): `opendata.amb.cat/api-amb/search/articles_NUMAMB`. 
   - **Acción:** Descarga la respuesta cruda para confirmar la estructura real del JSON (`count`, `items`) y los nombres exactos de los campos (`titol`, `description`, `numeroArticle`, `titolNormativa`). Ninguno de estos campos coincidía con la documentación inicial, por lo que este script fue vital para evitar errores de *parsing* posteriores.

2. **`extraer_candidatos.py`**
   - **Propósito:** Identificación y extracción de artículos legales.
   - **Acción:** Una vez identificados los artículos candidatos (305, 306, 307, 308, 309, 313) filtrando por `titolNormativa == "num_pgm.titol_4"` y cruzando sus títulos con la leyenda oficial de códigos `CLAU_URB`, este script extrae y limpia el texto completo de cada uno para permitir su revisión manual.

3. **`buscar_pendientes.py`**
   - **Propósito:** Resolución de referencias cruzadas y vacíos legales.
   - **Acción:** Extrae el Artículo 304 (al ser una referencia cruzada citada dentro del 306). Además, busca en los 574 artículos completos del PGM cualquier mención a la palabra "desenvolupament". Esto se hizo para intentar resolver las claves urbanísticas `19`, `20b` y `22b`, las cuales resultaron no tener un artículo general propio (se rigen por un Plan Parcial específico para cada parcela).

4. **`cargar_articulos_nuevos.py`**
   - **Propósito:** Ingesta de datos en la base de datos vectorial.
   - **Acción:** Carga los 7 artículos finales verificados (304, 305, 306, 307, 308, 309, 313) en la tabla `legal_chunks` de PostgreSQL, aplicando comprobación de duplicados. Es el único script de esta carpeta con valor operativo real más allá de la investigación inicial; se puede volver a ejecutar si es necesario reiniciar la base de datos.

5. **`probar_geocodificacion.py`**
   - **Propósito:** Pruebas de concepto (PoC) de sistemas de terceros.
   - **Acción:** Prueba independiente de la API de Nominatim (geocodificación inversa de coordenadas a direcciones) antes de programar el módulo oficial `backend/geo/geocoding.py`. Sirvió para confirmar empíricamente qué campos traía el *payload* real y validar si permitían identificar correctamente el distrito barcelonés.

---

## Hallazgos Clave (Lecciones Aprendidas de los Datos)

Estos descubrimientos técnicos no son obvios leyendo el código final del Backend, por lo que se documentan aquí para futuras referencias:

- **Limitaciones de la API Espacial:** El servicio `MapServer` del AMB que termina con el sufijo `_25831` es de **solo caché**; no soporta consultas dinámicas. Para interrogar a la base de datos geoespacial, es obligatorio usar la versión sin sufijo y emplear la operación `identify` de ArcGIS, no la operación `query`.
- **Zonas sin Normativa General:** Las claves urbanísticas `19`, `20b` y `22b` no poseen un artículo general. Son zonas de "desenvolupament" (desarrollo) que requieren un código único de planeamiento por parcela (existen decenas de ellos agrupados en `num_pgm.titol_8`). No se pueden clasificar como una categoría aplicable a toda la ciudad.
- **Interacciones CLI (Bash):** La herramienta `curl` en la terminal interpreta los corchetes `{ }` en una URL como una orden de expansión para múltiples peticiones simultáneas. Para llamar al endpoint `identify` del AMB manualmente desde la consola sin que la sintaxis JSON reviente, es imprescindible usar el flag `-g` (desactiva el *globbing*).