"""
Despacho y Control de Bodega
─────────────────────────────
Muestra los pedidos confirmados por los preventistas (Estado = "ASIGNADO")
pendientes de entrega física. Al confirmar el despacho:
  1. Cambia Estado → "Despachado" en compras_maestras.json
  2. Descuenta la cantidad del Stock físico en productos.json
"""
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
from utils.file_utils import safe_write_json, safe_read_json

st.title("Despacho")
st.markdown(
    "Gestiona la salida física de mercancía. Solo los pedidos en estado **Asignado** "
    "aparecen aquí — confirmar el despacho descuenta el stock del inventario."
)

# ── Acceso ────────────────────────────────────────────────────────────────────
role = st.session_state.get("user_info", {}).get("role", "")
if role not in ["ADMINISTRADOR", "DUEÑO", "BODEGA", "SUPERVISOR"]:
    st.error("Acceso denegado.")
    st.stop()

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent
MAESTROS_DIR  = BASE_DIR / "datos_maestros"
COMPRAS_PATH  = MAESTROS_DIR / "compras_maestras.json"
PRODUCTOS_PATH = MAESTROS_DIR / "productos.json"

# ── Cargar datos ──────────────────────────────────────────────────────────────
df_compras  = safe_read_json(COMPRAS_PATH)
df_productos = safe_read_json(PRODUCTOS_PATH)

if df_compras.empty:
    st.info("No hay datos en compras_maestras.json todavía.")
    st.stop()

if "Estado" not in df_compras.columns:
    st.warning("Los datos no tienen columna 'Estado'. Verifica la fuente de datos.")
    st.stop()

df_compras["Fecha"] = pd.to_datetime(df_compras["Fecha"], errors="coerce")

# Pedidos asignados (pendientes de despacho)
df_asig = df_compras[df_compras["Estado"].str.upper() == "ASIGNADO"].copy()

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — Resumen ejecutivo
# ════════════════════════════════════════════════════════════════════════════
total_pedidos = df_asig["NoPedido"].nunique() if not df_asig.empty else 0
total_clientes = df_asig["ClienteNombre"].nunique() if not df_asig.empty else 0
total_unidades = int(df_asig["Cantidad"].sum()) if not df_asig.empty else 0
total_valor = df_asig["Total"].sum() if not df_asig.empty else 0

b1, b2, b3, b4 = st.columns(4)
b1.metric("🛒 Pedidos por despachar", total_pedidos)
b2.metric("👥 Clientes distintos", total_clientes)
b3.metric("📦 Unidades totales", f"{total_unidades:,}")
b4.metric("💰 Valor comprometido", f"${total_valor:,.0f}")

if df_asig.empty:
    st.success("✅ No hay pedidos pendientes de despacho.")
    st.stop()

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — Filtros
# ════════════════════════════════════════════════════════════════════════════
st.markdown("### 🔎 Filtrar pedidos a despachar")

fechas_disponibles = sorted(
    df_asig["Fecha"].dt.date.dropna().unique().tolist(), reverse=True
)
rutas_disponibles = ["Todas"] + sorted(
    df_asig["Ruta"].dropna().astype(str).unique().tolist()
) if "Ruta" in df_asig.columns else ["Todas"]

cf1, cf2 = st.columns(2)
with cf1:
    fecha_sel = st.selectbox(
        "📅 Fecha del pedido",
        fechas_disponibles,
        format_func=lambda d: d.strftime("%A %d/%m/%Y").capitalize(),
    )
with cf2:
    ruta_sel = st.selectbox("🗺️ Ruta / Zona", rutas_disponibles)

# Aplicar filtros
df_filtrado = df_asig[df_asig["Fecha"].dt.date == fecha_sel].copy()
if ruta_sel != "Todas" and "Ruta" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["Ruta"].astype(str) == ruta_sel]

if df_filtrado.empty:
    st.info("No hay pedidos ASIGNADOS para ese filtro.")
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3 — Detalle por pedido
# ════════════════════════════════════════════════════════════════════════════
st.markdown(f"### 📋 Pedidos del {fecha_sel.strftime('%d/%m/%Y')} — {ruta_sel}")

pedidos_unicos = df_filtrado["NoPedido"].unique().tolist()

# Resumen por pedido (una fila = un pedido)
resumen_pedidos = (
    df_filtrado.groupby("NoPedido")
    .agg(
        Cliente=("ClienteNombre", "first"),
        Barrio=("Barrio", "first"),
        Ruta=("Ruta", "first"),
        Vendedor=("Vendedor", "first"),
        Unidades=("Cantidad", "sum"),
        Total=("Total", "sum"),
        Lineas=("CodigoProducto", "count"),
    )
    .reset_index()
    .sort_values("Cliente")
)

# Selector de pedidos a despachar
st.markdown("**Selecciona los pedidos a confirmar:**")
todos_check = st.checkbox("Seleccionar todos", value=True, key="check_todos")

pedidos_sel = []
for _, row in resumen_pedidos.iterrows():
    estado_li = "✅" if todos_check else "⬜"
    checked = st.checkbox(
        f"**{row['NoPedido']}** — {row['Cliente']}  |  "
        f"{int(row['Unidades'])} unds  |  ${row['Total']:,.0f}  |  {row['Barrio']}",
        value=todos_check,
        key=f"chk_{row['NoPedido']}",
    )
    if checked:
        pedidos_sel.append(row["NoPedido"])

if not pedidos_sel:
    st.warning("Selecciona al menos un pedido para despachar.")
    st.stop()

# Detalle consolidado de lo que se va a despachar
df_a_despachar = df_filtrado[df_filtrado["NoPedido"].isin(pedidos_sel)]

with st.expander(f"🔍 Ver detalle línea a línea ({len(df_a_despachar)} líneas)", expanded=False):
    cols_show = [c for c in ["NoPedido", "ClienteNombre", "CodigoProducto", "Producto", "Cantidad", "PrecioBase", "Total", "MetodoPago"]
                 if c in df_a_despachar.columns]
    st.dataframe(
        df_a_despachar[cols_show].sort_values(["NoPedido", "Producto"]),
        use_container_width=True, hide_index=True
    )

# Resumen de impacto en stock
st.markdown("#### 📦 Impacto en Stock Físico")
impacto_stock = (
    df_a_despachar.groupby("CodigoProducto")
    .agg(Producto=("Producto", "first"), TotalUnidades=("Cantidad", "sum"))
    .reset_index()
    .sort_values("TotalUnidades", ascending=False)
)
if not df_productos.empty and "Codigo" in df_productos.columns:
    df_productos["Codigo"] = df_productos["Codigo"].astype(str)
    impacto_stock["CodigoProducto"] = impacto_stock["CodigoProducto"].astype(str)
    impacto_stock = impacto_stock.merge(
        df_productos[["Codigo", "Stock"]].rename(columns={"Codigo": "CodigoProducto"}),
        on="CodigoProducto", how="left"
    )
    impacto_stock["Stock"] = impacto_stock["Stock"].fillna(0)
    impacto_stock["StockResultante"] = impacto_stock["Stock"] - impacto_stock["TotalUnidades"]

    # Alerta de stock insuficiente
    sin_stock = impacto_stock[impacto_stock["StockResultante"] < 0]
    if not sin_stock.empty:
        st.error(
            f"⚠️ **{len(sin_stock)} producto(s) quedarían con stock negativo** si se confirma "
            f"este despacho. Verifica el inventario físico antes de continuar."
        )
        st.dataframe(
            sin_stock[["Producto", "Stock", "TotalUnidades", "StockResultante"]],
            use_container_width=True, hide_index=True
        )
    else:
        st.success("✅ Stock suficiente para cubrir todos los productos del despacho.")

    st.dataframe(
        impacto_stock[["CodigoProducto", "Producto", "Stock", "TotalUnidades", "StockResultante"]].rename(
            columns={"Stock": "Stock Actual", "TotalUnidades": "A Despachar", "StockResultante": "Stock Final"}
        ),
        use_container_width=True, hide_index=True
    )
else:
    st.dataframe(impacto_stock[["CodigoProducto", "Producto", "TotalUnidades"]], use_container_width=True, hide_index=True)

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4 — Confirmación del Despacho
# ════════════════════════════════════════════════════════════════════════════
n_ped_sel = len(pedidos_sel)
n_und_sel = int(df_a_despachar["Cantidad"].sum())
val_sel   = df_a_despachar["Total"].sum()

st.markdown(
    f"**Resumen del despacho a confirmar:**  "
    f"{n_ped_sel} pedido(s) · {n_und_sel:,} unidades · ${val_sel:,.0f}"
)

confirmar = st.button(
    f"✅ Confirmar Despacho de {n_ped_sel} pedido(s)",
    type="primary",
    use_container_width=True,
)

if confirmar:
    with st.spinner("Procesando despacho..."):
        # 1. Actualizar Estado en compras_maestras.json
        df_maestro = safe_read_json(COMPRAS_PATH)
        if df_maestro.empty:
            st.error("No se pudo leer compras_maestras.json para actualizar.")
            st.stop()

        mask_desp = (
            df_maestro["NoPedido"].isin(pedidos_sel) &
            (df_maestro["Estado"].str.upper() == "ASIGNADO")
        )
        lineas_actualizadas = mask_desp.sum()
        df_maestro.loc[mask_desp, "Estado"] = "Despachado"

        ok_compras = safe_write_json(df_maestro, COMPRAS_PATH)
        if not ok_compras:
            st.error("No se pudo escribir compras_maestras.json (timeout de bloqueo). Intenta de nuevo.")
            st.stop()

        # 2. Descontar Stock físico en productos.json
        ok_stock = True
        if not df_productos.empty and "Codigo" in df_productos.columns:
            df_prod_upd = safe_read_json(PRODUCTOS_PATH)
            df_prod_upd["Codigo"] = df_prod_upd["Codigo"].astype(str)
            if "Stock" not in df_prod_upd.columns:
                df_prod_upd["Stock"] = 0

            for _, row in impacto_stock.iterrows():
                idx = df_prod_upd.index[df_prod_upd["Codigo"] == str(row["CodigoProducto"])]
                if not idx.empty:
                    df_prod_upd.loc[idx, "Stock"] = (
                        df_prod_upd.loc[idx, "Stock"].astype(float) - float(row["TotalUnidades"])
                    )

            ok_stock = safe_write_json(df_prod_upd, PRODUCTOS_PATH)

        # 3. Resultado
        if ok_compras and ok_stock:
            st.success(
                f"🚛 **Despacho confirmado exitosamente.**\n\n"
                f"- {lineas_actualizadas} líneas marcadas como **Despachado**\n"
                f"- {n_und_sel:,} unidades descontadas del stock físico\n"
                f"- {n_ped_sel} pedido(s) cerrados"
            )
            st.cache_data.clear()
            st.rerun()
        elif ok_compras and not ok_stock:
            st.warning(
                "El Estado de los pedidos se actualizó, pero hubo un error al escribir "
                "productos.json. Verifica el stock manualmente en el Gestor Base Maestra."
            )
        else:
            st.error("Error inesperado durante el despacho. Revisa los archivos manualmente.")

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5 — Historial de despachos recientes
# ════════════════════════════════════════════════════════════════════════════
st.markdown("---")
with st.expander("📂 Historial de despachos recientes (últimos 7 días)", expanded=False):
    hace7 = date.today() - timedelta(days=7)
    df_desp_hist = df_compras[
        (df_compras["Estado"].str.upper() == "DESPACHADO") &
        (df_compras["Fecha"].dt.date >= hace7)
    ]
    if df_desp_hist.empty:
        st.info("Sin despachos registrados en los últimos 7 días.")
    else:
        hist_res = (
            df_desp_hist.groupby(df_desp_hist["Fecha"].dt.date)
            .agg(
                Pedidos=("NoPedido", "nunique"),
                Clientes=("ClienteNombre", "nunique"),
                Unidades=("Cantidad", "sum"),
                Total=("Total", "sum"),
            )
            .reset_index()
            .rename(columns={"Fecha": "Día"})
            .sort_values("Día", ascending=False)
        )
        st.dataframe(
            hist_res.style.format({"Total": "${:,.0f}", "Unidades": "{:,.0f}"}),
            use_container_width=True, hide_index=True
        )

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 6 — Migración de datos heredados (solo ADMINISTRADOR / DUEÑO)
# Cierra pedidos ASIGNADO / TOMADO_PREVENTISTA de fechas pasadas que nunca
# pasaron por el flujo de despacho, para que no inflen StockAsignado.
# ════════════════════════════════════════════════════════════════════════════
if role in ["ADMINISTRADOR", "DUEÑO"]:
    st.markdown("---")
    with st.expander("🛠️ Mantenimiento: cerrar pedidos heredados sin despacho", expanded=False):
        st.markdown(
            "Si existen pedidos con estado **ASIGNADO** o **TOMADO_PREVENTISTA** de días "
            "anteriores que nunca pasaron por esta pantalla de despacho, quedan "
            "bloqueando el Stock Disponible indefinidamente. "
            "Esta acción los marca como **Finalizado** sin tocar el inventario físico "
            "(ya salieron de bodega en su momento)."
        )

        df_legacy = df_compras[
            df_compras["Estado"].str.upper().isin(["ASIGNADO", "TOMADO_PREVENTISTA"]) &
            (df_compras["Fecha"].dt.date < date.today())
        ]

        if df_legacy.empty:
            st.success("✅ No hay pedidos heredados pendientes de cierre.")
        else:
            n_ped_leg = df_legacy["NoPedido"].nunique()
            n_lin_leg = len(df_legacy)
            fecha_min_leg = df_legacy["Fecha"].min().date()
            fecha_max_leg = df_legacy["Fecha"].max().date()

            st.warning(
                f"Se encontraron **{n_ped_leg} pedido(s)** ({n_lin_leg} líneas) "
                f"con estado sin cerrar entre **{fecha_min_leg}** y **{fecha_max_leg}**."
            )

            with st.expander("Ver detalle de pedidos heredados"):
                cols_leg = [c for c in ["NoPedido", "Fecha", "ClienteNombre", "Producto", "Cantidad", "Estado"]
                            if c in df_legacy.columns]
                st.dataframe(df_legacy[cols_leg], use_container_width=True, hide_index=True)

            if st.button("✅ Marcar todos como Finalizado", type="secondary", key="btn_legacy"):
                df_maestro_leg = safe_read_json(COMPRAS_PATH)
                mask_leg = (
                    df_maestro_leg["Estado"].str.upper().isin(["ASIGNADO", "TOMADO_PREVENTISTA"]) &
                    (pd.to_datetime(df_maestro_leg["Fecha"], errors="coerce").dt.date < date.today())
                )
                df_maestro_leg.loc[mask_leg, "Estado"] = "Finalizado"
                if safe_write_json(df_maestro_leg, COMPRAS_PATH):
                    st.success(f"✅ {mask_leg.sum()} líneas cerradas como **Finalizado**.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("No se pudo escribir el archivo. Intenta de nuevo.")
