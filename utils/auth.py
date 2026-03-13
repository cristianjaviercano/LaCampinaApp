USERS = {
    "admin": {
        "password": "admin",
        "role": "ADMINISTRADOR",
        "access": ["Dashboard", "Inventario", "Clientes", "Rutas", "Reporte_Compras"]
    },
    "dueño": {
        "password": "dueno123",
        "role": "DUEÑO",
        "access": ["Dashboard", "Inventario", "Clientes", "Rutas", "Reporte_Compras"]
    },
    "propietario": {
        "password": "prop123",
        "role": "DUEÑO",
        "access": ["Dashboard", "Inventario", "Clientes", "Rutas"]
    },
    "supervisor": {
        "password": "super123",
        "role": "SUPERVISOR",
        "access": ["Dashboard", "Inventario", "Rutas", "Reporte_Compras"]
    },
    "vendedor1": {
        "password": "vend123",
        "role": "VENDEDOR",
        "access": ["Dashboard", "Rutas", "Clientes"]
    },
    "contador": {
        "password": "conta123",
        "role": "CONTADOR",
        "access": ["Dashboard"] # Dashboard represents Ventas/Reportes for now
    },
    "bodega1": {
        "password": "bodega123",
        "role": "BODEGA",
        "access": ["Inventario"]
    },
    "demo": {
        "password": "demo123",
        "role": "DEMO",
        "access": ["Dashboard"]
    }
}

def authenticate(username, password):
    """
    Verifica si las credenciales son válidas.
    Retorna el diccionario de usuario si es correcto, None en caso contrario.
    """
    user = USERS.get(username)
    if user and user["password"] == password:
        return user
    return None
