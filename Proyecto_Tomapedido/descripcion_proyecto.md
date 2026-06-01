# Proyecto Tomapedido: APP La Campiña

Este documento describe a detalle el contexto de negocio, el impacto operativo y las especificaciones funcionales del módulo **Tomapedido** (Preventa Móvil) integrado en el ecosistema digital de **La Campiña**.

---

## 1. Descripción del Proyecto

El **Proyecto Tomapedido** es el núcleo de digitalización comercial de **La Campiña**, diseñado para transformar el canal tradicional de distribución mayorista y minorista (tienda a tienda - TaT). Su objetivo principal es dotar al equipo de preventistas de una herramienta móvil ágil, intuitiva y resiliente que les permita capturar pedidos en campo, consultar inventarios en tiempo real, aplicar políticas comerciales dinámicas (como combos, bundles y promociones) y geolocalizar sus visitas, asegurando que toda la información se integre automáticamente al backend y al sistema de despacho y optimización de rutas del almacén central.

---

## 2. La Importancia del Tomapedido en la Última Milla

En los modelos de distribución tradicionales de consumo masivo, la **última milla** no comienza en el camión de reparto; comienza en la **captura de la demanda (preventa)**. Una toma de pedidos deficiente genera ineficiencias críticas que destruyen el margen operativo en las fases posteriores de la cadena de suministro.

La importancia del módulo Tomapedido en la optimización de la última milla radica en:

### A. Sincronía del Inventario (Reducción de Quiebres y Devoluciones)
* **El problema:** Si el preventista vende productos agotados o con existencias erróneas, se generan entregas parciales, rechazos de mercancía en el punto de entrega y costos de logística inversa (devoluciones).
* **El valor del Tomapedido:** Al estar conectado con el stock físico del almacén, el preventista asegura la viabilidad física del despacho desde el instante de la venta.

### B. Georreferenciación y Rutas de Despacho Eficientes
* **El problema:** La falta de orden geográfico en la venta causa que los camiones de reparto recorran rutas redundantes, cruzándose en zonas similares o subutilizando la capacidad cúbica de los vehículos.
* **El valor del Tomapedido:** Capturar las coordenadas exactas de cada cliente durante la preventa alimenta el motor de optimización de rutas de última milla, permitiendo planificar despachos agrupados por sectores geográficos.

### C. Velocidad de Transmisión de Datos
* **El problema:** Tomar pedidos en papel u hojas de cálculo sin sincronizar retrasa el armado de pedidos (picking) en bodega. Esto acorta la ventana de entrega de última milla y sobrecarga el trabajo nocturno de despacho.
* **El valor del Tomapedido:** La transmisión instantánea de datos permite que el equipo de bodega prepare despachos de manera continua durante el día (wave picking), optimizando los tiempos de cargue y despacho a primera hora de la mañana.

---

## 3. Descripción Operativa del Producto Digital

Operativamente, el producto digital se compone de tres interfaces integradas que habilitan un flujo continuo:

```
[Preventista en Campo] ──(Pedidos e Hilos GPS)──> [Servidor/Base de Datos] ──(Consolidado de Carga)──> [Bodega y Rutas]
```

### A. Flujo del Preventista (Frontend Móvil/Web)
1. **Inicio de Jornada y Sincronización:** El preventista inicia sesión, descarga la base maestra actualizada de clientes, inventarios y promociones vigentes para garantizar operatividad.
2. **Navegación de Rutas:** La app presenta los clientes asignados para el día organizados por secuencia de visita lógica.
3. **Visita al Cliente:**
   * **Registro de Visita:** Se captura la ubicación GPS y la hora de inicio de la interacción.
   * **Toma de Pedido:** Se agregan productos al carrito de compras. El sistema calcula subtotales, aplica promociones automáticas por volumen o combos de forma transparente y verifica límites de crédito.
   * **Cierre de Pedido / Visita No Efectiva:** Si el cliente compra, se firma digitalmente el pedido. Si no compra, el preventista debe seleccionar una justificación estandarizada (ej. negocio cerrado, stock completo, falta de liquidez).
4. **Sincronización:** Los pedidos se transmiten al servidor central.

### B. Flujo del Supervisor / Administrador (Panel de Control Web)
1. **Monitoreo en Tiempo Real:** El administrador visualiza en un mapa interactivo el avance de las visitas del equipo comercial (clientes visitados, efectividad de venta, montos vendidos).
2. **Gestión de Políticas Comerciales:** Configuración de promociones complejas (ej. "lleva 10 cajas de producto A y obtén 1 caja de producto B con 50% de descuento") con aplicación automática e inmediata en las terminales preventistas.
3. **Gestión de Cartera de Clientes:** Actualización de cupos de crédito, plazos de pago y estados de cuentas pendientes.

### C. Flujo de Despacho y Logística (Back-Office)
1. **Filtro y Aprobación:** Los pedidos recibidos pasan por validación automática de crédito e inventario.
2. **Consolidación de Carga (Picking):** Se genera la lista general de picking para que el personal de bodega prepare los cargamentos consolidados por ruta física.
3. **Optimización de Rutas de Entrega:** Los pedidos aprobados se introducen al algoritmo de optimización de rutas (ej. mediante algoritmos de ruteo de vehículos VRP), el cual genera el itinerario exacto y el orden de cargue de los camiones (último en entrar al camión, primero en entregarse).
