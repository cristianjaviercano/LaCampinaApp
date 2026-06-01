# [Devs Manual] - Ecosistema Tomapedido & Despacho La Campiña

Este manual sirve como especificación de diseño formal y guía de desarrollo para el equipo encargado de construir el producto digital **Tomapedido** (Preventa) y **Despacho** para **La Campiña**.

---

## 📋 Tabla de Contenidos

Este manual técnico se divide en cuatro secciones de diseño técnico (TDD):

### 1. [Arquitectura y Estructura de Datos (TDD-01)](tdd-01_arquitectura_y_datos.md)
*   **Stack Tecnológico:** React Native, Expo, NativeWind (Tailwind), SQLite local (WatermelonDB), API backend en Node/Python y base de datos central PostgreSQL en la nube.
*   **Arquitectura de Alto Nivel:** Modelo relacional cliente-servidor con sincronización automática offline-first.
*   **Estructura de Carpetas:** Monorepo de componentes y servicios compartidos.
*   **Esquema de BD:** Tablas e índices para usuarios, clientes, inventario, pedidos, logística (OTIF) y rendimiento de preventistas (OEE).

### 2. [Flujos Lógicos y Pseudocódigo (TDD-02)](tdd-02_flujos_y_pseudocodigo.md)
*   **Diagramas de Secuencia:** Flujos de sincronización de pedidos y aplicación de promociones complejas.
*   **Mapeo de Controladores y Modelos:** Archivos físicos clave.
*   **Pseudocódigo de Desarrollo:** Lógicas de sincronización atómica de base de datos, motor local de ofertas (combos/bonos) y consolidado logístico de picking.

### 3. [Seguridad y Permisos (TDD-03)](tdd-03_seguridad_y_permisos.md)
*   **Matriz RBAC (Gobernanza):** Definición detallada de privilegios a nivel de filas y columnas (CRUD) para Vendedores, Supervisores, Bodegueros, Choferes y Administradores.
*   **Seguridad de Endpoints:** Middleware de autenticación JWT y guardia de roles de autorización.
*   **Flujo de Auditoría:** Registro de transacciones delicadas (Logs) con comparativa de valores previos y posteriores.

### 4. [Analítica y Manual Operativo (TDD-04)](tdd-04_analitica_y_manual_operativo.md)
*   **Fórmulas SQL de KPIs:** Consultas para el OEE de vendedores, OTIF de camiones, volumen diario facturado y en peso físico, ticket promedio de compra e inventario.
*   **Tablero de Control:** Estructura de payloads JSON para el frontend React.
*   **Manual de Soporte / DevOps:** Comandos básicos de inicialización y despliegue del entorno local, junto con especificaciones de tareas automatizadas (Cron jobs).

---

## 🛠️ Entradas Operativas del Producto

*   **Aplicación Preventista (Móvil):** Opera de manera local sin conexión de red. Almacena en cola de base de datos local y transmite peticiones al detectar red.
*   **Consolidación Logística (Web):** Genera listados de carga agrupando la suma de productos por ruta física (Picking optimizado).
*   **Auditoría Contable:** Sistema de control de saldo de crédito y control estricto de edición de precios restringido por roles.
