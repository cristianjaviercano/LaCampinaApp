# TDD-04: Analítica y Manual Operativo - Sistema Tomapedido La Campiña

Este documento técnico de diseño (TDD) especifica el cálculo de KPIs mediante consultas SQL, las estructuras de comunicación API para los tableros de control y la guía de operaciones DevOps del sistema.

---

## 1. Diseño de KPIs y Extracción de Datos (Consultas SQL)

Para poblar el dashboard gerencial y administrativo de La Campiña, el motor de base de datos ejecutará las siguientes consultas SQL agregadas de forma periódica o en tiempo real.

### KPI A: OEE de Vendedores (Disponibilidad × Rendimiento × Calidad)
*Calcula el desempeño diario consolidado de un vendedor basado en visitas reales sobre programadas y efectividad.*
```sql
SELECT 
    seller_id,
    work_date,
    -- Disponibilidad: Tiempos operativos en ruta (simulado o registrado)
    availability_score, 
    -- Rendimiento: Proporción de visitas realizadas vs visitas asignadas
    ROUND((actual_visits::decimal / NULLIF(scheduled_visits, 0)) * 100, 2) AS performance_score,
    -- Calidad: Efectividad de la venta (clientes que compraron / visitas reales)
    ROUND((effective_sales::decimal / NULLIF(actual_visits, 0)) * 100, 2) AS quality_score,
    -- OEE General
    ROUND((availability_score * (actual_visits::decimal / NULLIF(scheduled_visits, 0)) * (effective_sales::decimal / NULLIF(actual_visits, 0))), 2) AS overall_oee
FROM seller_oee_metrics
WHERE work_date = CURRENT_DATE;
```

### KPI B: OTIF de Camiones (On-Time In-Full)
*Calcula el cumplimiento logístico por camión y ruta de despacho.*
```sql
SELECT 
    t.plate AS truck_plate,
    t.driver_name,
    COUNT(dd.id) AS total_deliveries,
    -- A tiempo
    ROUND((COUNT(CASE WHEN dd.is_delivered_on_time = TRUE THEN 1 END)::decimal / COUNT(dd.id)) * 100, 2) AS on_time_percentage,
    -- Completo
    ROUND((COUNT(CASE WHEN dd.is_delivered_in_full = TRUE THEN 1 END)::decimal / COUNT(dd.id)) * 100, 2) AS in_full_percentage,
    -- OTIF Promedio
    ROUND(AVG(dd.otif_score), 2) AS otif_average
FROM delivery_details dd
JOIN dispatches d ON dd.dispatch_id = d.id
JOIN trucks t ON d.truck_id = t.id
WHERE d.dispatch_date = CURRENT_DATE
GROUP BY t.plate, t.driver_name;
```

### KPI C: Volumen Total de Venta (Dinero y Peso) al Día
*Mide el volumen de carga consolidada para logística de cargue y facturación diaria.*
```sql
SELECT 
    COUNT(o.id) AS total_orders,
    SUM(o.total_amount) AS total_revenue_cop,
    -- Peso consolidado estimando un peso promedio por unidad de producto o columna de peso
    SUM(oi.quantity * COALESCE(p.price * 0.15, 1.0)) AS total_weight_kg -- Simulación peso
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
WHERE DATE(o.order_date) = CURRENT_DATE AND o.status != 'RECHAZADO';
```

### KPI D: Ticket Promedio de Compra por Tienda
```sql
SELECT 
    c.id AS client_id,
    c.business_name,
    ROUND(AVG(o.total_amount), 2) AS average_ticket_cop
FROM orders o
JOIN clients c ON o.client_id = c.id
WHERE o.status != 'RECHAZADO'
GROUP BY c.id, c.business_name
ORDER BY average_ticket_cop DESC;
```

### KPI E: Top 10 Productos Más Vendidos (SKUs)
```sql
SELECT 
    p.sku,
    p.name AS product_name,
    SUM(oi.quantity) AS total_units_sold,
    SUM(oi.quantity * oi.price_unit) AS total_revenue_generated
FROM order_items oi
JOIN products p ON oi.product_id = p.id
JOIN orders o ON oi.order_id = o.id
WHERE DATE(o.order_date) >= CURRENT_DATE - INTERVAL '30 days' AND o.status != 'RECHAZADO'
GROUP BY p.sku, p.name
ORDER BY total_units_sold DESC
LIMIT 10;
```

---

## 2. Especificación de APIs y Componentes de UI (Dashboards)

Para visualizar estas métricas de forma atractiva en el Frontend Web (construido en React y Tailwind CSS), se aconseja integrar la librería **Recharts** o **Chart.js**.

### Estructura de Payload JSON para Tablero General (`GET /api/metrics/dashboard`)
```json
{
  "summary": {
    "totalRevenue": 45200000.00,
    "totalWeightKg": 3240.50,
    "totalOrders": 124,
    "averageTicket": 364500.00
  },
  "sellerOee": [
    { "sellerName": "Daifer Geney", "oee": 88.5, "effectiveSales": 18, "visits": 20 },
    { "sellerName": "Junior Marquez", "oee": 92.0, "effectiveSales": 19, "visits": 20 }
  ],
  "truckOtif": [
    { "plate": "TRK-001", "driver": "Pedro Gomez", "otif": 95.0, "onTime": 98.0, "inFull": 97.0 },
    { "plate": "TRK-002", "driver": "Carlos Perez", "otif": 89.2, "onTime": 90.0, "inFull": 99.0 }
  ],
  "topProducts": [
    { "sku": "GA-01", "name": "Gaseosa Cola 1.5L", "quantity": 1200 },
    { "sku": "AG-02", "name": "Agua Mineral 500ml", "quantity": 850 }
  ]
}
```

---

## 3. Manual Técnico de Operación y Tareas Programadas (DevOps)

### A. Tareas Cron programadas (Nightly Jobs)

El sistema operativo del servidor ejecutará las siguientes rutinas de sincronización y optimización diariamente a la medianoche (`00:00 AM`).

```bash
# 1. Sincronización de cartera y stock con el ERP contable
0 0 * * * curl -X POST https://api.lacampina.com/api/sync/erp -H "Authorization: Bearer $CRON_TOKEN"

# 2. Cierre automático de visitas activas de vendedores (Vendedores que no hicieron Check-out)
5 0 * * * curl -X POST https://api.lacampina.com/api/sync/auto-checkout -H "Authorization: Bearer $CRON_TOKEN"

# 3. Purga y archivado automático de registros históricos a tablas frías (pedidos > 180 días)
30 0 * * * curl -X POST https://api.lacampina.com/api/archive/old-orders -H "Authorization: Bearer $CRON_TOKEN"
```

### B. Inicialización del Entorno de Desarrollo Local

Para "encender" el proyecto monorepo de desarrollo por primera vez, el ingeniero del equipo debe ejecutar los siguientes comandos:

```bash
# 1. Clonar el repositorio e instalar las dependencias generales
git clone https://github.com/cristianjaviercano/LaCampinaApp.git
cd LaCampinaApp
npm install

# 2. Configurar las variables de entorno locales
cp apps/backend-api/.env.example apps/backend-api/.env

# 3. Levantar la base de datos PostgreSQL local usando Docker Compose
docker-compose up -d database

# 4. Correr las migraciones iniciales de la base de datos SQL
npm run db:migrate --workspace=backend-api

# 5. Ejecutar semilla de datos iniciales (Usuarios de prueba, Catálogo base)
npm run db:seed --workspace=backend-api

# 6. Encender el servidor backend y frontend web en modo desarrollo
npm run dev
```
