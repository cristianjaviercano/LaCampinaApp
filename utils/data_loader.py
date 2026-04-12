import streamlit as st
import pandas as pd
from pathlib import Path

# Rutas base
BASE_DIR = Path(__file__).resolve().parent.parent
MAESTROS_DIR = BASE_DIR / "datos_maestros"

# ─────────────────────────────────────────────────────────────────────────────
# DATOS MAESTROS (permanentes, cambian solo via Gestor Base Maestra)
# ─────────────────────────────────────────────────────────────────────────────


@st.cache_data(ttl=None)  # sin expiración — solo se limpia con "Refrescar Caché"
def load_maestros():
    """
    Carga las tres bases de datos maestras (ubicaciones, vendedores, productos)
    desde datos_maestros/. Estos datos son estables y no cambian con cada lote.
    """
    try:
        ubicaciones_path = MAESTROS_DIR / "ubicaciones.json"
        vendedores_path = MAESTROS_DIR / "vendedores.json"
        productos_path = MAESTROS_DIR / "productos.json"
        clientes_path = MAESTROS_DIR / "clientes_maestro.json"

        df_ubicaciones = (
            pd.read_json(ubicaciones_path)
            if ubicaciones_path.exists()
            else pd.DataFrame()
        )
        df_vendedores = (
            pd.read_json(vendedores_path)
            if vendedores_path.exists()
            else pd.DataFrame()
        )
        df_productos = (
            pd.read_json(productos_path) if productos_path.exists() else pd.DataFrame()
        )
        df_clientes = (
            pd.read_json(clientes_path) if clientes_path.exists() else pd.DataFrame()
        )

        if not df_clientes.empty:
            # Deduplicate by Codigo, keeping first row with non-null Nombre
            df_clientes = df_clientes.sort_values(
                by=["Codigo", "Nombre"], na_position="last"
            ).drop_duplicates(subset="Codigo", keep="first")

        if not df_ubicaciones.empty and "Ciudad" in df_ubicaciones.columns:
            df_ubicaciones["Ciudad"] = df_ubicaciones["Ciudad"].str.upper().str.strip()
            df_ubicaciones["Ciudad"] = (
                df_ubicaciones["Ciudad"]
                .str.replace("Á", "A")
                .str.replace("É", "E")
                .str.replace("Í", "I")
                .str.replace("Ó", "O")
                .str.replace("Ú", "U")
            )

        if not df_clientes.empty and "Ciudad" in df_clientes.columns:
            df_clientes["Ciudad"] = df_clientes["Ciudad"].str.upper().str.strip()
            df_clientes["Ciudad"] = (
                df_clientes["Ciudad"]
                .str.replace("Á", "A")
                .str.replace("É", "E")
                .str.replace("Í", "I")
                .str.replace("Ó", "O")
                .str.replace("Ú", "U")
            )

        return {
            "ubicaciones": df_ubicaciones,
            "vendedores": df_vendedores,
            "productos": df_productos,
            "clientes": df_clientes,
        }
    except Exception as e:
        st.error(f"Error cargando datos maestros: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# COMPRAS (transaccional — se actualiza al cargar nuevo Purchase Order)
# Filtra por rango de fechas si se indica; por defecto devuelve todas.
# ─────────────────────────────────────────────────────────────────────────────


@st.cache_data(ttl=None)
def load_compras(fecha_inicio=None, fecha_fin=None):
    """
    Carga el historial de compras_maestras.json Y acumula de forma dinámica
    todos los lotes cargados en la carpeta datos_historicos.
    Consolida una macro-base de datos con toda la información.
    """
    dfs = []

    # 1. Cargar Base Maestra de Compras (si existe)
    compras_path = MAESTROS_DIR / "compras_maestras.json"
    if compras_path.exists():
        try:
            df_maestro = pd.read_json(compras_path)
            if not df_maestro.empty:
                dfs.append(df_maestro)
        except Exception as e:
            st.error(f"Error cargando compras_maestras.json: {e}")

    # 2. Iterar y apilar todos los lotes de datos_historicos/
    historicos_dir = BASE_DIR / "datos_historicos"
    if historicos_dir.exists():
        for batch_dir in historicos_dir.iterdir():
            if batch_dir.is_dir():
                det_path = batch_dir / "compras_detalle.json"
                if det_path.exists():
                    try:
                        df_det = pd.read_json(det_path)
                        if not df_det.empty:
                            # Mapear nombres del histórico al estándar de la aplicación
                            df_det = df_det.rename(
                                columns={
                                    "PurchaseOrderID": "NoPedido",
                                    "OrderDate": "Fecha",
                                    "LineTotal": "Total",
                                    "DiaRuta": "Ruta",
                                    "ProductoNombre": "Producto",
                                    "ProductoCodigo": "CodigoProducto",
                                }
                            )
                            # Rellenar columnas faltantes para que el concat sea limpio
                            if "ClienteNombre" not in df_det.columns:
                                df_det["ClienteNombre"] = "Cliente " + df_det[
                                    "ClienteCodigo"
                                ].astype(str)
                            if "CodigoVendedor" not in df_det.columns:
                                df_det["CodigoVendedor"] = ""
                            if "Estado" not in df_det.columns:
                                df_det["Estado"] = "Finalizado"
                            if "PctDescuento" not in df_det.columns:
                                df_det["PctDescuento"] = 0

                            dfs.append(df_det)
                    except Exception as e:
                        st.warning(
                            f"Error leyendo el lote histórico {batch_dir.name}: {e}"
                        )

    if not dfs:
        st.warning(
            "No hay datos de compras cargados. Ve a 'Carga de Datos' o al Gestor Maestro para subir la información."
        )
        return None, None

    try:
        # Concatenar toda la macro-base operativa
        df = pd.concat(dfs, ignore_index=True)
        # Limpiar duplicados exactos (por si un archivo se coló doble)
        df = df.drop_duplicates()

        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

        if "Ciudad" in df.columns:
            df["Ciudad"] = df["Ciudad"].str.upper().str.strip()
            df["Ciudad"] = (
                df["Ciudad"]
                .str.replace("Á", "A")
                .str.replace("É", "E")
                .str.replace("Í", "I")
                .str.replace("Ó", "O")
                .str.replace("Ú", "U")
            )

        if fecha_inicio:
            df = df[df["Fecha"] >= pd.to_datetime(fecha_inicio)]
        if fecha_fin:
            df = df[df["Fecha"] <= pd.to_datetime(fecha_fin)]

        # ── compras (cabecera de pedido: una fila por pedido resumida) ──────────────
        df_compras = (
            df.groupby(
                [
                    "NoPedido",
                    "Fecha",
                    "ClienteCodigo",
                    "ClienteNombre",
                    "Barrio",
                    "Ciudad",
                    "Ruta",
                    "CodigoVendedor",
                    "Vendedor",
                    "MetodoPago",
                    "Estado",
                ],
                dropna=False,
            )
            .agg(TotalPedido=("Total", "sum"))
            .reset_index()
        )
        # Renombres para compatibilidad con los dashboards existentes
        df_compras.rename(
            columns={
                "NoPedido": "NoPedido",
                "ClienteCodigo": "ClienteCodigo",
                "ClienteNombre": "Nombre",
            },
            inplace=True,
        )

        # ── compras_detalle (todas las líneas exactas) ────────────────────────────
        df_detalle = df.copy()

        return df_compras, df_detalle

    except Exception as e:
        st.error(f"Error uniendo y procesando la macro-base de compras: {e}")
        return None, None


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN UNIFICADA — mantiene compatibilidad con el resto de la app
# ─────────────────────────────────────────────────────────────────────────────


@st.cache_data(ttl=3600)
def load_data(fecha_historica=None):
    """
    Punto de entrada único para todos los dashboards.
    - Bases maestras: siempre desde datos_maestros/
    - Compras: desde compras_maestras.json (filtrable en dashboards)
    - fecha_historica se mantiene por compatibilidad pero ya no es la única fuente.
    """
    maestros = load_maestros()
    if maestros is None:
        return None

    df_compras, df_detalle = load_compras()
    if df_compras is None:
        df_compras = pd.DataFrame()
        df_detalle = pd.DataFrame()

    # Merge with clientes to ensure ClienteNombre is the full name from maestros
    df_clientes = maestros.get("clientes", pd.DataFrame())
    if not df_detalle.empty and not df_clientes.empty:
        df_detalle = df_detalle.merge(
            df_clientes[["Codigo", "Nombre"]],
            left_on="ClienteCodigo",
            right_on="Codigo",
            how="left",
        )
        df_detalle["ClienteNombre"] = df_detalle["Nombre"].fillna(
            df_detalle["ClienteNombre"]
        )
        df_detalle.drop(
            columns=["Nombre", "Codigo"],
            inplace=True,
            errors="ignore",
        )

    if not df_compras.empty and not df_clientes.empty:
        df_compras = df_compras.merge(
            df_clientes[["Codigo", "Nombre"]],
            left_on="ClienteCodigo",
            right_on="Codigo",
            how="left",
            suffixes=("_orig", "_maestro"),
        )
        df_compras["Nombre"] = df_compras["Nombre_maestro"].fillna(
            df_compras["Nombre_orig"]
        )
        df_compras.drop(
            columns=["Nombre_orig", "Nombre_maestro", "Codigo"],
            inplace=True,
            errors="ignore",
        )

    return {
        # Bases maestras (estables)
        "clientes": maestros.get("clientes", pd.DataFrame()),
        "ubicaciones": maestros.get("ubicaciones", pd.DataFrame()),
        "vendedores": maestros.get("vendedores", pd.DataFrame()),
        "productos": maestros.get("productos", pd.DataFrame()),
        # Transaccional
        "compras": df_compras,
        "compras_detalle": df_detalle,
    }
