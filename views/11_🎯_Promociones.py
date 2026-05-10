"""
Gestor de Promociones Comerciales
──────────────────────────────────
El administrador crea dos tipos de promo:
  • Bundle   — agrupa N SKUs con un precio especial de combo
  • Descuento — aplica un % de rebaja a un SKU de baja rotación

Las promos activas y vigentes aparecen automáticamente en el Módulo
Preventista como impulso de venta.
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import uuid
from utils.promos import load_promos, save_promo, delete_promo, toggle_promo
from utils.data_loader import load_data

st.title("Promociones")
st.markdown(
    "Define combos de productos y descuentos por baja rotación. "
    "Las promos vigentes aparecen en tiempo real en el terminal del preventista."
)

# ── Acceso ────────────────────────────────────────────────────────────────────
role = st.session_state.get("user_info", {}).get("role", "")
if role not in ["ADMINISTRADOR", "DUEÑO"]:
    st.error("Acceso restringido a perfiles gerenciales.")
    st.stop()

# ── Datos de productos ────────────────────────────────────────────────────────
data = load_data()
df_prod = data["productos"].copy() if data else pd.DataFrame()
if not df_prod.empty:
    df_prod["Codigo"] = df_prod["Codigo"].astype(str)
    df_prod["PrecioBase"] = pd.to_numeric(df_prod.get("PrecioBase", 0), errors="coerce").fillna(0)

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — Promos existentes
# ════════════════════════════════════════════════════════════════════════════
promos = load_promos()
hoy = date.today()

st.markdown("### 📋 Promociones configuradas")

if not promos:
    st.info("No hay promociones creadas todavía. Usa el formulario de abajo para crear la primera.")
else:
    for promo in promos:
        vigente = False
        try:
            fi = date.fromisoformat(promo["fecha_inicio"])
            ff = date.fromisoformat(promo["fecha_fin"])
            vigente = fi <= hoy <= ff
        except Exception:
            pass

        activo  = promo.get("activo", False)
        tipo    = promo.get("tipo", "descuento")
        tipo_icon = "🎁" if tipo == "bundle" else "🏷️"

        if activo and vigente:
            borde = "#22c55e"; fondo = "#f0fdf4"; badge_c = "#16a34a"; badge_t = "#dcfce7"; badge_txt = "ACTIVA"
        elif activo and not vigente:
            borde = "#f59e0b"; fondo = "#fffbeb"; badge_c = "#b45309"; badge_t = "#fef3c7"; badge_txt = "FUERA DE VIGENCIA"
        else:
            borde = "#d1d5db"; fondo = "#f9fafb"; badge_c = "#6b7280"; badge_t = "#f3f4f6"; badge_txt = "INACTIVA"

        # Resumen de productos
        prods_txt = ", ".join(
            f"{p.get('cantidad', 1)}× {p['nombre']}" for p in promo.get("productos", [])
        )
        precio_info = (
            f"Precio especial: **${promo.get('precio_especial', 0):,.0f}**"
            if tipo == "bundle"
            else f"Descuento: **{promo.get('descuento_pct', 0)}%**"
        )

        with st.container():
            st.markdown(f"""
            <div style="background:{fondo}; border:1px solid {borde}; border-left:5px solid {borde};
                        border-radius:10px; padding:14px 18px; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                        <span style="font-size:1.05rem; font-weight:700; color:#111;">
                            {tipo_icon} {promo['nombre']}
                        </span>
                        &nbsp;<span style="font-size:0.72rem; background:{badge_t}; color:{badge_c};
                                         padding:2px 8px; border-radius:10px; font-weight:600;">
                            {badge_txt}
                        </span>
                        &nbsp;<span style="font-size:0.72rem; color:#6b7280; background:#f3f4f6;
                                         padding:2px 8px; border-radius:10px;">
                            {tipo.upper()}
                        </span>
                    </div>
                    <span style="font-size:0.78rem; color:#6b7280;">
                        {promo.get('fecha_inicio', '')} → {promo.get('fecha_fin', '')}
                    </span>
                </div>
                <div style="margin-top:6px; font-size:0.85rem; color:#374151;">
                    📦 {prods_txt}<br>
                    💰 {precio_info}
                </div>
                <div style="margin-top:4px; font-size:0.82rem; color:#6b7280; font-style:italic;">
                    {promo.get('descripcion', '')}
                </div>
            </div>
            """, unsafe_allow_html=True)

            c_tog, c_del, _ = st.columns([1, 1, 4])
            lbl_tog = "⏸️ Desactivar" if activo else "▶️ Activar"
            if c_tog.button(lbl_tog, key=f"tog_{promo['id']}", use_container_width=True):
                nuevo = toggle_promo(promo["id"])
                st.success(f"Promo **{promo['nombre']}** {'activada' if nuevo else 'desactivada'}.")
                st.rerun()
            if c_del.button("🗑️ Eliminar", key=f"del_{promo['id']}", use_container_width=True):
                delete_promo(promo["id"])
                st.success(f"Promo **{promo['nombre']}** eliminada.")
                st.rerun()

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — Crear nueva promo
# ════════════════════════════════════════════════════════════════════════════
st.markdown("### ➕ Crear nueva promoción")

tipo_nueva = st.radio(
    "Tipo de promoción:",
    ["🎁 Bundle (Combo de productos)", "🏷️ Descuento por SKU"],
    horizontal=True,
)
es_bundle = tipo_nueva.startswith("🎁")

with st.form("form_promo", clear_on_submit=True):
    f1, f2 = st.columns(2)
    nombre_promo = f1.text_input("Nombre de la promo *", placeholder="ej: Combo Temporada Alta")
    descripcion  = f2.text_input("Descripción (aparece en terminal del vendedor)", placeholder="ej: Ideal para tiendas grandes")

    f3, f4 = st.columns(2)
    fecha_ini = f3.date_input("Fecha inicio", value=hoy)
    fecha_fin = f4.date_input("Fecha fin", value=hoy + timedelta(days=30))

    st.markdown("**Productos incluidos:**")

    # Selector de productos
    if df_prod.empty:
        st.warning("No hay catálogo de productos cargado. Sube primero el maestro de productos.")
        opciones_prod = []
    else:
        df_prod_act = df_prod[df_prod.get("Activo", pd.Series(1, index=df_prod.index)).fillna(1).astype(int) == 1] if "Activo" in df_prod.columns else df_prod
        opciones_prod = [
            f"{row['Codigo']} | {row['Nombre']} | ${row['PrecioBase']:,.0f}"
            for _, row in df_prod_act.iterrows()
        ]

    if es_bundle:
        st.caption("Selecciona entre 2 y 6 productos para el combo.")
        prods_sel = st.multiselect("Productos del bundle:", opciones_prod, max_selections=6)
        cantidades: dict[str, int] = {}
        if prods_sel:
            st.markdown("Cantidades por producto:")
            cols_qty = st.columns(min(len(prods_sel), 3))
            for i, ps in enumerate(prods_sel):
                nombre_p = ps.split(" | ")[1]
                cantidades[ps] = cols_qty[i % 3].number_input(
                    nombre_p[:20], min_value=1, value=1, step=1, key=f"qty_{i}"
                )

        # Calcular precio normal y mostrar sugerencia
        precio_normal = 0
        if prods_sel and not df_prod.empty:
            for ps in prods_sel:
                cod = ps.split(" | ")[0]
                row = df_prod[df_prod["Codigo"] == cod]
                if not row.empty:
                    precio_normal += float(row.iloc[0]["PrecioBase"]) * cantidades.get(ps, 1)

        if precio_normal > 0:
            st.caption(f"Precio normal suma: **${precio_normal:,.0f}** — define el precio especial del combo:")
        precio_especial = st.number_input(
            "Precio especial del combo ($) *",
            min_value=0.0,
            value=round(precio_normal * 0.85) if precio_normal > 0 else 0.0,
            step=500.0,
            format="%.0f",
        )
        descuento_pct_val = 0.0

    else:
        # Descuento simple por SKU
        prods_sel = st.multiselect("Producto a descontar:", opciones_prod, max_selections=1)
        cantidades = {ps: 1 for ps in prods_sel}
        descuento_pct_val = st.slider("Porcentaje de descuento (%)", min_value=1, max_value=60, value=15)
        precio_especial = 0.0
        if prods_sel and not df_prod.empty:
            cod = prods_sel[0].split(" | ")[0]
            row = df_prod[df_prod["Codigo"] == cod]
            if not row.empty:
                pb = float(row.iloc[0]["PrecioBase"])
                st.caption(f"Precio normal: ${pb:,.0f} → Precio con descuento: **${pb*(1-descuento_pct_val/100):,.0f}**")

    submitted = st.form_submit_button("✅ Guardar Promoción", type="primary", use_container_width=True)

if submitted:
    errores = []
    if not nombre_promo.strip():
        errores.append("El nombre es obligatorio.")
    if not prods_sel:
        errores.append("Debes seleccionar al menos un producto.")
    if es_bundle and precio_especial <= 0:
        errores.append("El precio especial del combo debe ser mayor que cero.")
    if fecha_fin < fecha_ini:
        errores.append("La fecha de fin no puede ser anterior a la de inicio.")

    if errores:
        for e in errores:
            st.error(e)
    else:
        productos_promo = []
        for ps in prods_sel:
            partes = ps.split(" | ")
            cod = partes[0]
            nom = partes[1]
            precio_b = 0.0
            if not df_prod.empty:
                row = df_prod[df_prod["Codigo"] == cod]
                if not row.empty:
                    precio_b = float(row.iloc[0]["PrecioBase"])
            productos_promo.append({
                "codigo":     cod,
                "nombre":     nom,
                "cantidad":   cantidades.get(ps, 1),
                "precio_base": precio_b,
            })

        nueva_promo = {
            "id":             f"PROMO-{uuid.uuid4().hex[:8].upper()}",
            "nombre":         nombre_promo.strip(),
            "tipo":           "bundle" if es_bundle else "descuento",
            "activo":         True,
            "descripcion":    descripcion.strip(),
            "fecha_inicio":   fecha_ini.isoformat(),
            "fecha_fin":      fecha_fin.isoformat(),
            "productos":      productos_promo,
            "precio_especial": float(precio_especial),
            "descuento_pct":  float(descuento_pct_val),
        }
        save_promo(nueva_promo)
        st.success(f"✅ Promo **{nombre_promo}** creada y activa desde hoy.")
        st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3 — Vista previa del impacto
# ════════════════════════════════════════════════════════════════════════════
promos_activas = [p for p in load_promos() if p.get("activo")]
if promos_activas:
    st.markdown("---")
    with st.expander(f"👁️ Vista previa — lo que verá el preventista hoy ({len(promos_activas)} promo(s) activa(s))", expanded=False):
        for p in promos_activas:
            if p["tipo"] == "bundle":
                precio_norm = sum(x["cantidad"] * x.get("precio_base", 0) for x in p["productos"])
                ahorro = precio_norm - p["precio_especial"]
                pct_aho = ahorro / precio_norm * 100 if precio_norm > 0 else 0
                st.markdown(f"""
                <div style="background:#faf5ff; border:1px solid #a78bfa; border-left:4px solid #7c3aed;
                            border-radius:10px; padding:14px; margin-bottom:8px;">
                    <b style="color:#6d28d9;">🎁 {p['nombre']}</b><br>
                    <span style="font-size:0.85rem; color:#374151;">{p.get('descripcion','')}</span><br>
                    <span style="font-size:0.82rem; color:#6b7280;">
                        {' + '.join(f"{x['cantidad']}× {x['nombre']}" for x in p['productos'])}
                    </span><br>
                    <span style="color:#6d28d9; font-weight:600;">
                        💰 ${p['precio_especial']:,.0f}
                        <span style="text-decoration:line-through; color:#9ca3af; font-weight:400;
                                     font-size:0.85rem;"> ${precio_norm:,.0f} </span>
                        — ahorra ${ahorro:,.0f} ({pct_aho:.0f}%)
                    </span>
                </div>
                """, unsafe_allow_html=True)
            else:
                prod = p["productos"][0] if p["productos"] else {}
                pb = prod.get("precio_base", 0)
                pct = p.get("descuento_pct", 0)
                st.markdown(f"""
                <div style="background:#fff7ed; border:1px solid #fb923c; border-left:4px solid #ea580c;
                            border-radius:10px; padding:14px; margin-bottom:8px;">
                    <b style="color:#c2410c;">🏷️ {p['nombre']}</b><br>
                    <span style="font-size:0.85rem; color:#374151;">{p.get('descripcion','')}</span><br>
                    <span style="font-size:0.82rem; color:#6b7280;">{prod.get('nombre','')}</span><br>
                    <span style="color:#c2410c; font-weight:600;">
                        {pct:.0f}% OFF →
                        <span style="text-decoration:line-through; color:#9ca3af; font-weight:400;"> ${pb:,.0f} </span>
                        <b>${pb*(1-pct/100):,.0f}</b>
                    </span>
                </div>
                """, unsafe_allow_html=True)
