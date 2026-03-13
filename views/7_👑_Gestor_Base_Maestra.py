import streamlit as st
import pandas as pd
import json
from pathlib import Path

st.set_page_config(page_title="Gestor Base Maestra", page_icon="👑", layout="wide")
st.title("👑 Gestor de Bases de Datos Maestras")
st.markdown(
    "Aquí viven los tres catálogos permanentes de la empresa (**Ubicaciones**, **Vendedores**, **Productos**) "
    "y el histórico acumulado de **compras**. Edítalos sin necesidad de recargar todo el sistema cada vez."
)

if st.session_state.get("user_info", {}).get("role") not in ["ADMINISTRADOR", "DUEÑO"]:
    st.error("Acceso DENEGADO. Solo perfiles gerenciales pueden alterar las Bases Maestras.")
    st.stop()

# ─── Rutas ───────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent
MAESTROS    = BASE_DIR / "datos_maestros"
MAESTROS.mkdir(exist_ok=True)

PATHS = {
    "ubicaciones": MAESTROS / "ubicaciones.json",
    "vendedores":  MAESTROS / "vendedores.json",
    "productos":   MAESTROS / "productos.json",
    "clientes":    MAESTROS / "clientes_maestro.json",
    "compras":     MAESTROS / "compras_maestras.json",
}

# ─── Helpers ─────────────────────────────────────────────────────────────────
def read_json(key):
    p = PATHS[key]
    if p.exists():
        return pd.read_json(p)
    return pd.DataFrame()

def save_json(df, key):
    df.to_json(PATHS[key], orient="records", force_ascii=False, indent=2)

def split_coordinates(coord):
    if pd.isna(coord):
        return pd.Series([None, None])
    parts = str(coord).split(",")
    if len(parts) == 2:
        try:
            return pd.Series([round(float(parts[0].strip()), 7),
                              round(float(parts[1].strip()), 7)])
        except ValueError:
            return pd.Series([None, None])
    return pd.Series([None, None])

def metrica(label, df, col_coord=None):
    total = len(df)
    if col_coord and not df.empty and col_coord[0] in df.columns:
        ok = int(df[col_coord].notna().all(axis=1).sum())
        return label, total, ok
    return label, total, None

# ─────────────────────────────────────────────────────────────────────────────
# TABS principales
# ─────────────────────────────────────────────────────────────────────────────
tab_ubi, tab_vend, tab_prod, tab_clientes, tab_compras = st.tabs([
    "📍 Ubicaciones de Tiendas",
    "👤 Vendedores",
    "📦 Productos",
    "👥 Clientes Maestros",
    "🧾 Historial de Compras (Purchase Order)",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 – UBICACIONES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ubi:
    st.subheader("📍 Base Maestra de Ubicaciones de Tiendas")
    st.markdown(
        "Contiene las coordenadas geográficas de cada punto de venta. "
        "Sube un nuevo Excel para actualizar masivamente o edita celdas directamente."
    )

    df_ubi = read_json("ubicaciones")

    # Métricas rápidas
    if not df_ubi.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("📍 Total Tiendas", len(df_ubi))
        coord_ok = int(df_ubi[["Latitud", "Longitud"]].notna().all(axis=1).sum()) if "Latitud" in df_ubi.columns else 0
        c2.metric("✅ Con Coordenadas", coord_ok)
        c3.metric("⚠️ Sin Coordenadas", len(df_ubi) - coord_ok)

    # Upload masivo
    with st.expander("⬆️ Actualizar masivamente desde Excel o CSV", expanded=False):
        st.markdown(
            "Acepta archivos con columnas `Nombre`/`NOMBRE`, `Barrio`, `DiaVisita`/`DIA_RUTA`, "
            "`Latitud`, `Longitud`. También acepta columna `COORDENADAS` en formato `lat, lon`."
        )
        f_ubi = st.file_uploader("Subir Archivo de Ubicaciones", type=["xlsx","xls","csv"], key="ubi_upload")
        if f_ubi:
            if f_ubi.name.endswith(".csv"):
                df_new = pd.read_csv(f_ubi)
            else:
                df_new = pd.read_excel(f_ubi)
            st.dataframe(df_new.head(5), use_container_width=True)
            if st.button("💾 Guardar como Ubicaciones Maestras", type="primary", key="btn_ubi"):
                with st.spinner("Procesando..."):
                    if "COORDENADAS" in df_new.columns:
                        df_new[["Latitud","Longitud"]] = df_new["COORDENADAS"].apply(split_coordinates)
                        df_new.drop(columns=["COORDENADAS"], inplace=True, errors="ignore")
                    df_new.rename(columns={"NOMBRE":"Nombre","BARRIO":"Barrio","DIA_RUTA":"DiaVisita"}, inplace=True)
                    if "Cliente" not in df_new.columns and "Nombre" in df_new.columns:
                        df_new.rename(columns={"Nombre":"Cliente"}, inplace=True)
                    df_new["NOMBRE_NORM"] = df_new["Cliente"].astype(str).str.strip().str.upper()
                    for col in ["Cliente","Barrio","DiaVisita","Latitud","Longitud","NOMBRE_NORM"]:
                        if col not in df_new.columns:
                            df_new[col] = None
                    save_json(df_new[["Cliente","Barrio","DiaVisita","Latitud","Longitud","NOMBRE_NORM"]], "ubicaciones")
                    st.cache_data.clear()
                    st.success(f"✅ ubicaciones.json actualizado — {len(df_new)} tiendas")
                    st.rerun()

    # Editor manual
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("**Editor en vivo:**")
    with c2:
        if not df_ubi.empty:
            st.download_button(
                label="⬇️ Descargar (.csv)",
                data=df_ubi.to_csv(index=False).encode("utf-8"),
                file_name="ubicaciones.csv",
                mime="text/csv",
                key="dl_ubi"
            )

    if not df_ubi.empty:
        df_ubi_edit = st.data_editor(df_ubi, num_rows="dynamic", use_container_width=True,
                                     height=450, key="editor_ubi")
        if st.button("💾 Guardar Cambios de Ubicaciones", key="save_ubi"):
            save_json(df_ubi_edit, "ubicaciones")
            st.cache_data.clear()
            st.success("✅ Ubicaciones guardadas correctamente.")
    else:
        st.info("No hay datos de ubicaciones. Sube un Excel para empezar.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 – VENDEDORES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_vend:
    st.subheader("👤 Base Maestra de Vendedores")
    st.markdown("Catálogo de la fuerza de ventas. Raramente cambia; se puede editar directamente.")

    df_vend = read_json("vendedores")

    if not df_vend.empty:
        c1, c2 = st.columns(2)
        activos = int(df_vend["Activo"].sum()) if "Activo" in df_vend.columns else len(df_vend)
        c1.metric("👤 Vendedores Totales", len(df_vend))
        c2.metric("✅ Activos", activos)

    with st.expander("⬆️ Actualizar desde Excel o CSV de Vendedores", expanded=False):
        st.markdown("Necesita columnas: `USUARIO (NUMÉRICO)`, `NOMBRE`, `TELÉFONO`, `PRESUPUESTO DE VENTAS`, `ACTIVO (1 = SI, 0 = NO)`")
        f_vend = st.file_uploader("Subir Archivo de Vendedores", type=["xlsx","xls","csv"], key="vend_upload")
        if f_vend:
            if f_vend.name.endswith(".csv"):
                df_vnew = pd.read_csv(f_vend)
            else:
                df_vnew = pd.read_excel(f_vend)
            st.dataframe(df_vnew.head(), use_container_width=True)
            if st.button("💾 Guardar como Vendedores Maestros", type="primary", key="btn_vend"):
                with st.spinner("Procesando..."):
                    col_map = {
                        "USUARIO (NUMÉRICO)":"Codigo",
                        "NOMBRE":"Nombre",
                        "TELÉFONO":"Telefono",
                        "PRESUPUESTO DE VENTAS":"Presupuesto",
                        "ACTIVO (1 = SI, 0 = NO)":"Activo",
                    }
                    df_new_v = df_vnew.rename(columns={k:v for k,v in col_map.items() if k in df_vnew.columns})
                    for col in ["Codigo","Nombre","Telefono","Presupuesto","Activo"]:
                        if col not in df_new_v.columns:
                            df_new_v[col] = None
                    save_json(df_new_v[["Codigo","Nombre","Telefono","Presupuesto","Activo"]], "vendedores")
                    st.cache_data.clear()
                    st.success(f"✅ vendedores.json actualizado — {len(df_new_v)} vendedores")
                    st.rerun()

    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("**Editor en vivo:**")
    with c2:
        if not df_vend.empty:
            st.download_button(
                label="⬇️ Descargar (.csv)",
                data=df_vend.to_csv(index=False).encode("utf-8"),
                file_name="vendedores.csv",
                mime="text/csv",
                key="dl_vend"
            )

    if not df_vend.empty:
        df_vend_edit = st.data_editor(df_vend, num_rows="dynamic", use_container_width=True,
                                      height=300, key="editor_vend")
        if st.button("💾 Guardar Cambios de Vendedores", key="save_vend"):
            save_json(df_vend_edit, "vendedores")
            st.cache_data.clear()
            st.success("✅ Vendedores guardados correctamente.")
    else:
        st.info("No hay datos de vendedores. Sube un Excel para empezar.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 – PRODUCTOS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_prod:
    st.subheader("📦 Base Maestra de Productos  (catálogo)")
    st.markdown("Catálogo completo de SKUs con precios y stock. Se puede ampliar cuando se agreguen nuevos productos.")

    df_prod = read_json("productos")

    if not df_prod.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Total SKUs", len(df_prod))
        activos_p = int(df_prod["Activo"].sum()) if "Activo" in df_prod.columns else len(df_prod)
        c2.metric("✅ Activos", activos_p)
        c3.metric("🔴 Inactivos", len(df_prod) - activos_p)

    with st.expander("⬆️ Actualizar desde Excel o CSV de Productos", expanded=False):
        st.markdown(
            "Necesita columnas: `CÓDIGO (Obligatorio)`, `NOMBRE (Obligatorio)`, "
            "`PRECIO BASE (Obligatorio)`, `PRECIO DE COMPRA DEL PRODUCTO`, "
            "`CANTIDAD EN INVENTARIO`, `PUNTO DE REORDEN`, `ACTIVO (1 = SI, 0 = NO)`, `UM`"
        )
        f_prod = st.file_uploader("Subir Archivo de Productos", type=["xlsx","xls","csv"], key="prod_upload")
        if f_prod:
            if f_prod.name.endswith(".csv"):
                df_pnew = pd.read_csv(f_prod)
            else:
                df_pnew = pd.read_excel(f_prod)
            st.dataframe(df_pnew.head(5), use_container_width=True)
            if st.button("💾 Guardar como Productos Maestros", type="primary", key="btn_prod"):
                with st.spinner("Procesando..."):
                    col_map = {
                        "CÓDIGO (Obligatorio)":              "Codigo",
                        "NOMBRE (Obligatorio)":              "Nombre",
                        "PRECIO BASE (Obligatorio)":         "PrecioBase",
                        "PRECIO DE COMPRA DEL PRODUCTO":     "PrecioCompra",
                        "CANTIDAD EN INVENTARIO":            "Stock",
                        "PUNTO DE REORDEN":                  "PuntoReorden",
                        "ACTIVO (1 = SI, 0 = NO)":           "Activo",
                        "UM":                                "UM",
                    }
                    df_new_p = df_pnew.rename(columns={k:v for k,v in col_map.items() if k in df_pnew.columns})
                    df_new_p["Codigo"] = df_new_p["Codigo"].astype(str).str.strip()
                    for col in ["Codigo","Nombre","PrecioBase","PrecioCompra","Stock","PuntoReorden","Activo","UM"]:
                        if col not in df_new_p.columns:
                            df_new_p[col] = None
                    save_json(df_new_p[["Codigo","Nombre","PrecioBase","PrecioCompra","Stock","PuntoReorden","Activo","UM"]], "productos")
                    st.cache_data.clear()
                    st.success(f"✅ productos.json actualizado — {len(df_new_p)} SKUs")
                    st.rerun()

    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("**Editor en vivo** (busca usando Ctrl+F en la tabla):")
    with c2:
        if not df_prod.empty:
            st.download_button(
                label="⬇️ Descargar (.csv)",
                data=df_prod.to_csv(index=False).encode("utf-8"),
                file_name="productos.csv",
                mime="text/csv",
                key="dl_prod"
            )

    if not df_prod.empty:
        # Filtro de búsqueda rápida
        buscar = st.text_input("🔍 Filtrar por nombre de producto", key="buscar_prod")
        df_prod_show = df_prod[df_prod["Nombre"].str.contains(buscar, case=False, na=False)] if buscar else df_prod
        df_prod_edit = st.data_editor(df_prod_show, num_rows="dynamic", use_container_width=True,
                                      height=500, key="editor_prod")
        if st.button("💾 Guardar Cambios de Productos", key="save_prod"):
            # Si hubo filtro, merge de vuelta con los originales
            if buscar:
                df_merged = df_prod.copy()
                df_merged.update(df_prod_edit.set_index(df_prod_edit.index))
                save_json(df_merged, "productos")
            else:
                save_json(df_prod_edit, "productos")
            st.cache_data.clear()
            st.success("✅ Catálogo de productos guardado correctamente.")
    else:
        st.info("No hay catálogo de productos. Sube un Excel para empezar.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 – CLIENTES MAESTROS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_clientes:
    st.subheader("👥 Base Maestra de Clientes")
    st.markdown(
        "Catálogo completo de clientes con información de contacto, ubicación geográfica y estado. "
        "Sube un Excel para actualizar masivamente o edita celdas directamente en la tabla."
    )

    df_cli = read_json("clientes")

    # Métricas rápidas
    if not df_cli.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("👥 Total Clientes", len(df_cli))
        activos_c = int(df_cli["Activo"].sum()) if "Activo" in df_cli.columns else len(df_cli)
        c2.metric("✅ Activos", activos_c)
        c3.metric("❌ Inactivos", len(df_cli) - activos_c)
        # Cobertura de coords
        if "Latitud" in df_cli.columns and "Longitud" in df_cli.columns:
            coords_ok = int(df_cli[["Latitud", "Longitud"]].notna().all(axis=1).sum())
            pct_geo = coords_ok / max(len(df_cli), 1) * 100
            c4.metric("📍 Georreferenciados", f"{coords_ok} ({pct_geo:.0f}%)")
        else:
            c4.metric("📍 Georreferenciados", "Sin datos de coords")

    # ── Upload masivo ──────────────────────────────────────────────────────────
    with st.expander("⬆️ Actualizar masivamente desde Excel o CSV de Clientes", expanded=False):
        st.markdown("""
        El archivo debe tener **al menos** las columnas:
        - `CÓDIGO CLIENTE` o `Codigo` — código único del cliente
        - `NOMBRE` o `NOMBRE CLIENTE` — nombre completo
        - `CIUDAD` (opcional), `BARRIO` (opcional), `RUTA` (opcional)
        - `TELÉFONO` (opcional), `NIT` (opcional)
        - `LATITUD` + `LONGITUD` (opcional) — o columna `COORDENADAS` en formato `lat, lon`
        - `ACTIVO` — 1=Sí, 0=No (opcional, por defecto 1)
        """)

        f_cli = st.file_uploader(
            "Subir Archivo de Clientes", type=["xlsx", "xls", "csv"], key="cli_upload"
        )

        if f_cli:
            if f_cli.name.endswith(".csv"):
                df_cnew = pd.read_csv(f_cli)
            else:
                df_cnew = pd.read_excel(f_cli)
            st.markdown(f"**Vista previa** — {len(df_cnew):,} filas encontradas:")
            st.dataframe(df_cnew.head(6), use_container_width=True)

            if st.button("💾 Guardar como Clientes Maestros", type="primary", key="btn_cli"):
                with st.spinner("Procesando clientes..."):
                    # ── Mapeo flexible de columnas ─────────────────────────────
                    col_map = {
                        # Codigo
                        "CÓDIGO CLIENTE":        "Codigo",
                        "CODIGO CLIENTE":         "Codigo",
                        "CÓDIGO":                 "Codigo",
                        "CODIGO":                 "Codigo",
                        "Código cliente":         "Codigo",
                        # Nombre
                        "NOMBRE CLIENTE":         "Nombre",
                        "NOMBRE":                 "Nombre",
                        "Nombre cliente":         "Nombre",
                        # Contacto
                        "TELÉFONO":               "Telefono",
                        "TELEFONO":               "Telefono",
                        "CELULAR":                "Telefono",
                        "NIT":                    "NIT",
                        # Ubicación
                        "CIUDAD":                 "Ciudad",
                        "Ciudad":                 "Ciudad",
                        "BARRIO":                 "Barrio",
                        "Barrio":                 "Barrio",
                        "RUTA":                   "Ruta",
                        "Ruta":                   "Ruta",
                        "DIRECCIÓN":              "Direccion",
                        "DIRECCION":              "Direccion",
                        # Coords
                        "LATITUD":                "Latitud",
                        "Latitud":                "Latitud",
                        "LONGITUD":               "Longitud",
                        "Longitud":               "Longitud",
                        "COORDENADAS":            "COORDENADAS",
                        # Estado
                        "ACTIVO (1 = SI, 0 = NO)": "Activo",
                        "ACTIVO":                 "Activo",
                        "Activo":                 "Activo",
                    }
                    df_proc = df_cnew.rename(
                        columns={k: v for k, v in col_map.items() if k in df_cnew.columns}
                    )

                    # Parsear columna COORDENADAS si existe
                    if "COORDENADAS" in df_proc.columns:
                        df_proc[["Latitud", "Longitud"]] = df_proc["COORDENADAS"].apply(split_coordinates)
                        df_proc.drop(columns=["COORDENADAS"], inplace=True, errors="ignore")

                    # Asegurar columnas mínimas
                    columnas_finales = [
                        "Codigo", "Nombre", "NIT", "Telefono",
                        "Ciudad", "Barrio", "Ruta", "Direccion",
                        "Latitud", "Longitud", "Activo"
                    ]
                    for col in columnas_finales:
                        if col not in df_proc.columns:
                            df_proc[col] = None

                    # Codigo limpio
                    df_proc["Codigo"] = df_proc["Codigo"].astype(str).str.strip()
                    # Activo default 1
                    df_proc["Activo"] = df_proc["Activo"].fillna(1).astype(int)

                    # Coords numéricas
                    for coord_col in ["Latitud", "Longitud"]:
                        df_proc[coord_col] = pd.to_numeric(df_proc[coord_col], errors="coerce")

                    # Conservar solo columnas finales
                    df_proc = df_proc[columnas_finales]

                    save_json(df_proc, "clientes")
                    st.cache_data.clear()

                    coords_ok_n = int(df_proc[["Latitud", "Longitud"]].notna().all(axis=1).sum())
                    st.success(
                        f"✅ clientes_maestro.json actualizado correctamente.\n\n"
                        f"- 👥 **{len(df_proc):,} clientes** cargados\n"
                        f"- 📍 **{coords_ok_n:,}** con coordenadas geográficas\n"
                        f"- ✅ **{int(df_proc['Activo'].sum()):,}** activos"
                    )
                    st.rerun()

    # ── Editor en vivo ────────────────────────────────────────────────────────
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("**Editor en vivo:**")
    with c2:
        if not df_cli.empty:
            st.download_button(
                label="⬇️ Descargar (.csv)",
                data=df_cli.to_csv(index=False).encode("utf-8"),
                file_name="clientes.csv",
                mime="text/csv",
                key="dl_cli"
            )

    if not df_cli.empty:
        buscar_cli = st.text_input("🔍 Filtrar por nombre de cliente", key="buscar_cli")
        df_cli_show = (
            df_cli[df_cli["Nombre"].astype(str).str.contains(buscar_cli, case=False, na=False)]
            if buscar_cli else df_cli
        )
        df_cli_edit = st.data_editor(
            df_cli_show, num_rows="dynamic", use_container_width=True,
            height=480, key="editor_cli"
        )
        if st.button("💾 Guardar Cambios de Clientes", key="save_cli"):
            if buscar_cli:
                df_merged_cli = df_cli.copy()
                df_merged_cli.update(df_cli_edit.set_index(df_cli_edit.index))
                save_json(df_merged_cli, "clientes")
            else:
                save_json(df_cli_edit, "clientes")
            st.cache_data.clear()
            st.success("✅ Base de clientes guardada correctamente.")

        # ── Reporte de calidad de datos ────────────────────────────────────────
        with st.expander("🔍 Reporte de calidad de datos de clientes", expanded=False):
            problemas = []
            if "Latitud" not in df_cli.columns or df_cli["Latitud"].isna().all():
                problemas.append("❌ Sin columna Latitud o todos los valores son nulos.")
            else:
                sin_lat = df_cli["Latitud"].isna().sum()
                if sin_lat > 0:
                    problemas.append(f"⚠️ {sin_lat} clientes sin Latitud.")
            if "Longitud" not in df_cli.columns or df_cli["Longitud"].isna().all():
                problemas.append("❌ Sin columna Longitud o todos los valores son nulos.")
            else:
                sin_lon = df_cli["Longitud"].isna().sum()
                if sin_lon > 0:
                    problemas.append(f"⚠️ {sin_lon} clientes sin Longitud.")
            if "Codigo" in df_cli.columns:
                dups = df_cli["Codigo"].duplicated().sum()
                if dups > 0:
                    problemas.append(f"⚠️ {dups} códigos duplicados detectados.")
            if "Nombre" in df_cli.columns:
                sin_nombre = df_cli["Nombre"].isna().sum()
                if sin_nombre > 0:
                    problemas.append(f"⚠️ {sin_nombre} clientes sin Nombre.")

            if problemas:
                for p in problemas:
                    st.warning(p)
            else:
                st.success("✅ Base de clientes en excelente estado. Sin problemas detectados.")
    else:
        st.info("No hay datos de clientes. Sube un Excel para comenzar.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 – HISTORIAL DE COMPRAS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_compras:
    st.subheader("🧾 Historial de Compras — Purchase Order Detail Report")
    st.markdown(
        "Este es el archivo transaccional que **sí se actualiza periódicamente**. "
        "Sube el reporte mensual de pedidos; el sistema lo acumula (o reemplaza) en `compras_maestras.json` "
        "desde donde todos los dashboards calculan las ventas por día, semana y mes."
    )

    df_comp = read_json("compras")

    # Estado actual
    if not df_comp.empty and "Fecha" in df_comp.columns:
        df_comp["Fecha"] = pd.to_datetime(df_comp["Fecha"], errors="coerce")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📋 Total Líneas", f"{len(df_comp):,}")
        total_ped = df_comp["NoPedido"].nunique() if "NoPedido" in df_comp.columns else "—"
        c2.metric("🛒 Pedidos Únicos", f"{total_ped:,}" if isinstance(total_ped, int) else total_ped)
        c3.metric("📅 Fecha Mínima", str(df_comp["Fecha"].min().date()))
        c4.metric("📅 Fecha Máxima", str(df_comp["Fecha"].max().date()))

        # Mini gráfico de actividad
        st.markdown("**Líneas de pedido por fecha:**")
        resumen = df_comp.groupby(df_comp["Fecha"].dt.date).size().reset_index(name="Lineas")
        resumen.columns = ["Fecha", "Lineas"]
        st.bar_chart(resumen.set_index("Fecha"))
        
        st.download_button(
            label="⬇️ Descargar Historial Completo (.csv)",
            data=df_comp.to_csv(index=False).encode("utf-8"),
            file_name="compras_historico.csv",
            mime="text/csv",
            key="dl_comp"
        )
    else:
        st.warning("No hay historial de compras cargado aún.")

    st.markdown("---")

    # Upload nuevo Purchase Order
    st.markdown("### ⬆️ Cargar nuevo Purchase Order Detail Report")

    modo = st.radio(
        "¿Qué hacer con los datos existentes?",
        ["➕ Acumular (agregar al histórico existente)", "🔄 Reemplazar (solo este mes)"],
        key="modo_compras",
        horizontal=True
    )

    f_po = st.file_uploader(
        "Subir Purchase Order Detail Report (.xlsx o .csv)",
        type=["xlsx","xls","csv"],
        key="po_upload"
    )

    if f_po:
        try:
            if f_po.name.endswith(".csv"):
                df_po = pd.read_csv(f_po)
            else:
                df_po = pd.read_excel(f_po)
            st.markdown(f"**Vista previa** — {len(df_po):,} líneas encontradas:")
            st.dataframe(df_po.head(8), use_container_width=True)

            col_min = pd.to_datetime(df_po["Fecha"], errors="coerce").min()
            col_max = pd.to_datetime(df_po["Fecha"], errors="coerce").max()
            st.info(f"📅 Rango del archivo: **{col_min.date()} → {col_max.date()}**  |  "
                    f"Fechas únicas: **{pd.to_datetime(df_po['Fecha'], errors='coerce').dt.date.nunique()}**")

            if st.button("⚙️ Procesar y Guardar Compras", type="primary", key="btn_po"):
                with st.spinner("Procesando Purchase Order..."):
                    # Normalizar al schema interno
                    df_nueva = pd.DataFrame({
                        "NoPedido":       df_po["No. Pedido"],
                        "Fecha":          pd.to_datetime(df_po["Fecha"], errors="coerce").dt.strftime("%Y-%m-%d"),
                        "ClienteCodigo":  df_po["Código cliente"].astype(str),
                        "ClienteNombre":  df_po["Nombre cliente"],
                        "Barrio":         df_po["Barrio"],
                        "Ciudad":         df_po["Ciudad"],
                        "Ruta":           df_po["Ruta"],
                        "CodigoVendedor": df_po["Código vendedor"].astype(str),
                        "Vendedor":       df_po["Vendedor"],
                        "CodigoProducto": df_po["Código producto"].astype(str).str.strip(),
                        "Producto":       df_po["Producto"],
                        "Cantidad":       df_po["Cantidad"],
                        "PrecioBase":     df_po["Precio base"],
                        "Total":          df_po["Total"],
                        "MetodoPago":     df_po["Método de pago"],
                        "Estado":         df_po["Estado"],
                        "PctDescuento":   df_po["% Descuentos"],
                    })

                    if "➕ Acumular" in modo and PATHS["compras"].exists():
                        df_existente = pd.read_json(PATHS["compras"])
                        df_final = pd.concat([df_existente, df_nueva], ignore_index=True)
                        # Eliminar duplicados exactos por NoPedido + CodigoProducto
                        df_final.drop_duplicates(
                            subset=["NoPedido","CodigoProducto"], keep="last", inplace=True
                        )
                        modo_txt = "acumulado"
                    else:
                        df_final = df_nueva
                        modo_txt = "reemplazado"

                    save_json(df_final, "compras")
                    st.cache_data.clear()

                    st.success(
                        f"✅ Historial de compras **{modo_txt}** exitosamente.\n\n"
                        f"- 📋 **{len(df_final):,} líneas** en total\n"
                        f"- 🛒 **{df_final['NoPedido'].nunique():,} pedidos** únicos\n"
                        f"- 📅 Rango: **{df_final['Fecha'].min()} → {df_final['Fecha'].max()}**"
                    )
                    st.rerun()

        except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")

    st.markdown("---")
    if not df_comp.empty:
        st.markdown("### 🗑️ Gestión avanzada")
        with st.expander("Eliminar registros de un rango de fechas (borrado por período)", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                fecha_del_start = st.date_input("Desde", key="del_start")
            with col_b:
                fecha_del_end = st.date_input("Hasta", key="del_end")
            if st.button("🗑️ Eliminar ese rango del histórico", type="secondary"):
                df_comp["Fecha"] = pd.to_datetime(df_comp["Fecha"], errors="coerce")
                mask = (df_comp["Fecha"].dt.date >= fecha_del_start) & (df_comp["Fecha"].dt.date <= fecha_del_end)
                eliminadas = mask.sum()
                df_comp = df_comp[~mask]
                save_json(df_comp, "compras")
                st.cache_data.clear()
                st.warning(f"Se eliminaron {eliminadas:,} líneas del rango seleccionado.")
                st.rerun()
