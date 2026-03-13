# Modelo Operativo y Conceptual: La Campiña v2.0 - Sistema de Gestión e Inteligencia de Negocios

Este documento presenta la fundamentación teórica, conceptual y metodológica detrás de la plataforma web analítica "APP La Campiña 2.0". El sistema está diseñado no solo como una herramienta de visualización (Dashboard), sino como un ecosistema de soporte a la toma de decisiones empresariales.

---

## 1. Fundamentación Teórica del Modelo

El sistema La Campiña opera bajo tres grandes pilares teóricos de la gestión moderna de cadenas de suministro (Supply Chain Management) y la Inteligencia de Negocios (Business Intelligence):

### 1.1. Inteligencia de Negocios (Business Intelligence - BI)
El pilar central del **Dashboard General** y del portal principal radica en la teoría de *Business Intelligence*. El modelo metodológico extrae los datos empíricos de operaciones (archivos Excel generados por sistemas ERP o puntos de venta físicos) y los procesa a través de un esquema de **ETL (Extracción, Transformación y Carga)**.
*   **Teoría Subyacente:** Transformar datos en información, e información en conocimiento accionable. Las métricas de "Ventas Totales", "Clientes Activos" y "Top Categorías" no son recuentos contables, sino *Key Performance Indicators (KPIs)* diseñados para desencadenar acciones gerenciales de alto nivel (como destinar presupuesto de marketing a la categoría menos vendida o potenciar la más fuerte).

### 1.2. Gestión Estratégica de Inventarios y Teoría de Colas
La sección de **Inventarios** de la plataforma se apoya en modelos de optimización de stock.
*   **Análisis Descriptivo Replicado:** Al graficar distribuciones de frecuencias poblacionales (como el Histograma de dispersión térmica de precios en el módulo Plotly de tu código), la aplicación permite un paneo estadístico del portafolio.
*   **Rotación de Activos:** La visualización de volúmenes de bodega vs referencias listadas se alinea con la *Teoría del Lote Económico del Pedido (EOQ)* de manera asintótica, ofreciendo la base visual para que los decisores eviten los dos grandes problemas logísticos: el coste de oportunidad del desabastecimiento (ruptura de stock) y el coste hundido del almacenamiento innecesario (sobrestock).

### 1.3. Inteligencia Geoespacial (Location Intelligence) y Enrutamiento (VRP)
El módulo de **Rutas** incorpora la disciplina de la Sistemas de Información Geográfica (GIS) aplicados a negocios.
*   **Problema de Enrutamiento de Vehículos (VRP - Vehicle Routing Problem) y TSP (Traveling Salesperson Problem):** Estás resolviendo (o planificando) un desafío matemático complejo. Mostrar en un plano (espacio Euclídeo mediante librerías Mapbox/Plotly) los puntos reales de los clientes (latitud y longitud) es el "Paso Cero" fundamental metodológicamente para calcular matrices de distancias, asignar zonas (clustering geográfico) de ventas a representantes e implementar algoritmos de última milla.
*   La metodología en tu módulo se centra en visualizar densidades de zonas.

---

## 2. Metodología Sistémica del Software

El desarrollo técnico se apoya en una metodología arquitectónica modular:

### 2.1. Arquitectura "Data-Agnostic" (Agnóstica a la base de datos)
El software está estructurado metodológicamente para estar **desacoplado** del sistema transaccional vivo. En lugar de estar conectado directamente mediante sentencias SQL a una pesada base de producción, el modelo opera sobre volúmenes masivos pasivos (`datos de prueba` en archivos .xlsx).
*   **Modelo de Cargue Masivo (Batch Loading):** Mediante la librería Pandas y tecnología de Caché en memoria viva de Python (usando anotaciones `@st.cache_data`), el código levanta megabytes de datos analíticos a RAM al instante de carga térmica y lo congela, mitigando la constante lectura de discos o estrés de red, permitiendo a la UI gráfica hacer *slices, dices* y procesamientos vectorizados matemáticos (Pandas / NumPy) en milésimas de segundo.

### 2.2. Paradigma Renderizado Orientado a Componentes y Flujo Inmersivo UI/UX
La interfaz de usuario usa **Streamlit** para romper el esquema normal (Cliente - Servidor - Base de Datos) de la web. En cambio la UI:
- Reacciona en tiempo real, recargando las dependencias direccionales al estado al más mínimo cambio (como selección mediante una caja de texto o interacción de botones).
- Emplea un **diseño responsivo apilable (Mobile-First):** Basado en expansores ocultos que empacan tablas masivas de datos en contenedores HTML5 que permiten leer resúmenes visuales rápidos, respondiendo al "Paradigma de Tableros Gerenciales": *Atender la vista macroscópica primero, consultar las tablas micro solo de ser necesario*.

---

## 3. Flujo Operativo Funcional

El modelo operativo que debe seguir el usuario/gerente para sacarle provecho a esta herramienta transcurre así:

1.  **Carga (ETL Off-line):** Las áreas correspondientes descargan (desde el software empresarial maestro) los reportes de ventas, vendedores e inventario en formato tabular puro `.xlsx` dentro de la carpeta segura `datos de prueba`.
2.  **Activación de la Memoria Caché:** Al dar inicio, el gestor `utils/data_loader.py` levanta, lee y correlaciona de manera pasiva los 5 ejes principales (VENDEDORES, CLIENTES, PRODUCTOS, ÓRDENES y UBICACIONES).
3.  **Procesamiento Analítico:** Las vistas (`pages/*.py`) actúan como consumidores agnósticos. Reciben el JSON o *DataFrame* del estado de la memoria, detectan sus columnas mediante heurísticas (comprobación de integridad), cruzan la información y arman tensores temporales (series de tiempo) operadas matemáticamente por la paquetería científica `numpy`.
4.  **Despliegue Gerencial Interactivo:** Una renderización veloz en D3.js y WebGL subyacente de los gráficos interactivos de Ploly para proyectarse en pantallas web o celulares remotos, finalizando el ciclo con los botones de limpieza de memoria (`Refrescar Datos`) que cierran la brecha para una próxima revisión operacional.

---

*En conclusión, APP La Campiña versión 2.0 no es un mero "mostrador" de datos tabulados; metodológicamente es un modelo reactivo, estático del lado del procesamiento crudo pero fluido del lado visual, diseñado expresamente en lenguaje científico y con herramientas propias del "Data Science" para llevar un negocio anclado en analítica transaccional al paradigma de "Decisiones Guiadas Por Datos" (Data-Driven Decision Making).*

---

## 4. Estructuras de Datos (Migración a JSON)

Para optimizar la carga y lectura de los datos, agilizar los tiempos en caché y estructurar la información sin modificar los archivos originales, la aplicación consumirá archivos `.json` generados a partir de los de prueba de Excel de la empresa. 

Las estructuras y el cruce relacional esperado son las siguientes:

### `clientes.json`
- `Codigo` *(desde CÓDIGO (Obligatorio))*
- `Nombre` *(desde NOMBRE DEL NEGOCIO)*
- `Ciudad` *(desde CIUDAD)*
- `Categoria` *(desde TIPO DE NEGOCIO)*
- `Activo` *(desde ACTIVO)*
- `Latitud` y `Longitud` *(Cruzado e identificado desde el archivo de UBICACIONES)*

### `compras.json`
- `PurchaseOrderID` *(desde No. Pedido)*
- `OrderDate` *(desde Fecha)*
- `LineTotal` *(desde Total)*
- `ClienteCodigo` *(desde Código cliente)*

### `productos.json`
- `Codigo` *(desde CÓDIGO)*
- `Nombre` *(desde NOMBRE)*
- `Categoria` *(desde CÓDIGO CATEGORÍA)*
- `Precio` *(desde PRECIO BASE)*
- `Stock` *(desde CANTIDAD EN INVENTARIO)*

### `ubicaciones.json`
- `Cliente` *(desde NOMBRE)*
- `Latitud` *(limpiado de COORDENADAS)*
- `Longitud` *(limpiado de COORDENADAS)*

### `vendedores.json`
- `Codigo` *(desde USUARIO)*
- `Nombre` *(desde NOMBRE)*

---

## 5. Estructura Analítica por Módulos y Potencial de Desarrollo

Con base en la robusta estructura de datos transaccional e indexada (JSON) implementada, a continuación se desglosa el alcance analítico actual de cada módulo y se formulan **propuestas de expansión analítica de alto valor añadido** que pueden desarrollarse para cada vista.

### 5.1 Módulo 1: Dashboard General (KPIs y Visión Global)
**Estructura Actual:**
- **Datos base:** Se nutre principalmente de `compras.json`, cruzado con conteos macro de `productos.json` y `clientes.json`.
- **Análisis presente:** Total monetario de ventas, conteo de órdenes activas, evolución temporal de los ingresos diarios (gráfico de líneas) y distribución de ventas por categoría de producto principal (gráfico de torta).

**Potencial de Análisis (Nuevas Métricas Sugeridas):**
- **Ticket Promedio:** Calcular la media del `LineTotal` por cada `PurchaseOrderID` para entender cuánto gasta un cliente en una sola transacción.
- **Análisis de Varianza Temporal:** Gráficos que comparen las ventas de la semana actual vs. la semana anterior.
- **Tasa de Crecimiento de Base de Clientes:** Evolución histórica mensual de nuevos clientes vs. clientes inactivos.
- **Métricas de Meta de Ventas (Gauge Chart):** Aprovechando si se integran datos de metas u objetivos por vendedor o por la empresa, visualizar el porcentaje actual alcanzado de la meta mensual.

### 5.2 Módulo 2: Inventario (Gestión de Stock y Catálogo)
**Estructura Actual:**
- **Datos base:** Se nutre exclusivamente de `productos.json`.
- **Análisis presente:** Disposición y filtrado interactivo del catálogo, recuento de stock en bodega, y un histograma de la distribución y frecuencia de los precios unitarios.

**Potencial de Análisis (Nuevas Métricas Sugeridas):**
- **Alerta de Rotura de Stock (Punto de Reorden):** Usar la columna `Stock` para generar alertas visuales (en rojo) de aquellos productos cuyo inventario está llegando a cero o por debajo de su punto de reorden.
- **Análisis ABC de Inventario:** Clasificar los productos dinámicamente:
  - **A:** Los productos que más beneficios dejan o mayor costo de bodega tienen.
  - **B:** Término medio.
  - **C:** Menos valiosos o estancados.
- **Valorización del Inventario:** Métrica del capital inmovilizado (suma de `Precio` o *Costo* multiplicada por las unidades de `Stock` actual).

### 5.3 Módulo 3: Clientes (Comportamiento y Cobertura)
**Estructura Actual:**
- **Datos base:** Se nutre fuertemente de `clientes.json`.
- **Análisis presente:** Conteo de base demográfica, clasificación horizontal por ciudades top con representación geográfica tabular, y distinción porcentual mediante categorías o "Tipos de Negocio".

**Potencial de Análisis (Nuevas Métricas Sugeridas):**
- **Análisis RFM (Recencia, Frecuencia, Valor Monetario):** Cruzando `clientes.json` con `compras.json`:
  - *Recencia:* ¿Hace cuántos días transó por última vez?
  - *Frecuencia:* ¿Cuántos pedidos ha realizado en el trimestre?
  - *Valor Monetario:* ¿Cuál es el volumen histórico facturado a ese código?
- **Matriz de Clientes Durmientes vs. Fieles:** Un Scatter Plot o Heatmap que exponga aquellos clientes que antes compraban mucho y ahora dejaron de hacerlo.
- **Penetración Demográfica por Barrio:** Bajar la granularidad analítica de la "Ciudad" al "Barrio" para dirigir campañas de mercadeo localizado.

### 5.4 Módulo 4: Rutas (Geolocalización y Optimización Logística)
**Estructura Actual:**
- **Datos base:** Depende enteramente de `ubicaciones.json` cruzado con perfiles de cliente activos e inactivos.
- **Análisis presente:** Plot geoespacial mediante mapa de burbujas interactivo, capaz de ubicar visualmente los establecimientos a visitar usando latitud y longitud explícita.

**Potencial de Análisis (Nuevas Métricas Sugeridas):**
- **Clusterización Geográfica (Zonificación Estática):** Con un simple cruce de "Día de Visita", colorear los puntos del mapa según si caen lunes, martes o miércoles, optimizando la asignación de vendedores por cuadrantes.
- **Mapa de Calor Comercial (Heatmap):** Superponer la densidad de ventas o el "Ticket Promedio" georreferenciado; esto mostrará de un vistazo en qué zonas (latitud/longitud) de la ciudad están los clientes de mayor volumen transaccional ("zonas calientes").
- **Estimación de Densidad y Rutas Más Densas:** Analizar con métricas de agrupamiento (ej. algoritmo KMeans sencillo sobre coordenadas) si hay clientes huérfanos muy alejados del cluster principal que sean costosos logísticamente frente al beneficio que traen.
