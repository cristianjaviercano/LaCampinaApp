# TDD-03: Seguridad, Permisos y Gobernanza - Sistema Tomapedido La Campiña

Este documento técnico de diseño (TDD) define el modelo de control de acceso basado en roles (RBAC), la gobernanza de datos y la seguridad a nivel de API para asegurar los datos sensibles del sistema.

---

## 1. Matriz de Control de Acceso (RBAC)

Para garantizar la jerarquización y protección de la información sensible (como precios, saldos de crédito de clientes y descuentos), se implementa la siguiente matriz de permisos CRUD (Crear, Leer, Actualizar, Borrar).

| Entidad / Datos | Preventista | Supervisor | Bodeguero | Chofer | Administrador |
|---|---|---|---|---|---|
| **Clientes (Fichas)** | Leer (Propios) | Leer / Actualizar | Sin Acceso | Leer (Dirección) | CRUD |
| **Cartera / Cupos de Crédito** | Leer (Propios) | Leer | Sin Acceso | Sin Acceso | CRUD |
| **Catálogo de Productos** | Leer | Leer | Leer | Sin Acceso | CRUD |
| **Precios de Productos** | Leer (Solo Ver) | Leer | Leer | Sin Acceso | CRUD (Editar) |
| **Promociones y Descuentos** | Leer (Ver combo) | Leer | Sin Acceso | Sin Acceso | CRUD (Crear/Editar) |
| **Pedidos** | Crear / Leer (Propios) | CRUD | Leer (Picking) | Leer | CRUD |
| **Despachos e Itinerarios** | Sin Acceso | CRUD | Leer / Actualizar | Leer / Actualizar | CRUD |
| **KPIs (OEE del Vendedor)** | Leer (Propio) | Leer (Todos) | Sin Acceso | Sin Acceso | Leer (Todos) |
| **KPIs (OTIF Camiones)** | Sin Acceso | Leer | Sin Acceso | Leer (Propio) | Leer (Todos) |
| **Logs de Auditoría** | Sin Acceso | Sin Acceso | Sin Acceso | Sin Acceso | Leer |

---

## 2. Lógica de Middlewares y Protección de Rutas

Todas las rutas de la API (excepto `/api/auth/login`) requieren un encabezado de autorización `Authorization: Bearer <JWT>`. La API valida la firma del token y aplica validación de rol (RBAC) en tiempo de ejecución.

### Pseudocódigo de Middleware de Autenticación (`auth.middleware.ts`)
```typescript
import { Request, Response, NextFunction } from 'express';
import * as jwt from 'jsonwebtoken';

interface UserPayload {
  userId: number;
  username: string;
  role: string;
}

export function verifyJwtMiddleware(req: Request, res: Response, next: NextFunction) {
  const authHeader = req.headers['authorization'];
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ message: 'Token de acceso no proporcionado.' });
  }

  const token = authHeader.split(' ')[1];

  try {
    const secret = process.env.JWT_SECRET || 'super-secret-key-la-campina';
    const decoded = jwt.verify(token, secret) as UserPayload;
    
    // Adjuntar la información del usuario autenticado a la petición
    req.user = decoded;
    next();
  } catch (error) {
    return res.status(401).json({ message: 'Token inválido o expirado.' });
  }
}
```

### Pseudocódigo de Middleware de Autorización por Roles (`roles.guard.ts`)
```typescript
import { Request, Response, NextFunction } from 'express';

// Decorador o función validadora de permisos por endpoint
export function authorizeRoles(allowedRoles: string[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    const user = req.user; // Cargado por verifyJwtMiddleware
    
    if (!user) {
      return res.status(401).json({ message: 'Usuario no autenticado.' });
    }

    if (!allowedRoles.includes(user.role.toUpperCase())) {
      return res.status(403).json({ 
        message: `Acceso denegado: El rol '${user.role}' no tiene permisos para esta acción.` 
      });
    }

    next();
  };
}

// Ejemplo de uso para proteger la edición de precios:
// router.put('/products/:id/price', verifyJwtMiddleware, authorizeRoles(['ADMINISTRADOR']), editPriceHandler);
```

---

## 3. Flujo de Auditoría (Audit Logs)

Para rastrear cambios críticos en información financiera (cartera, saldos de clientes y aplicación de descuentos manuales), el sistema cuenta con un disparador o listener que escribe en la tabla `audit_logs` del esquema.

### Estructura de la Tabla de Auditoría
```sql
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,          -- 'ACTUALIZAR_PRECIO', 'AJUSTAR_CREDITO', 'CREAR_PROMO'
    table_name VARCHAR(50) NOT NULL,      -- 'products', 'clients', 'promotions'
    record_id INTEGER NOT NULL,            -- ID de la fila afectada
    ip_address VARCHAR(45),
    before_value_json JSONB,              -- Estado del registro antes del cambio
    after_value_json JSONB,               -- Estado del registro después del cambio
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Lógica de Captura del Log (Pseudocódigo en Service)
```typescript
class AuditService {
  async logTransaction(
    dbConnection: Database,
    userId: number,
    action: string,
    tableName: string,
    recordId: number,
    beforeState: any,
    afterState: any,
    ip: string
  ): Promise<void> {
    const query = `
      INSERT INTO audit_logs (user_id, action, table_name, record_id, before_value_json, after_value_json, ip_address)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
    `;
    await dbConnection.query(query, [
      userId,
      action,
      tableName,
      recordId,
      JSON.stringify(beforeState),
      JSON.stringify(afterState),
      ip
    ]);
  }
}
```
