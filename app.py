import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import requests
import copy

# Set page config
st.set_page_config(
    page_title="Dashboard Censo 2024 - Tenencia de Vivienda y Brecha Digital",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Title styling */
    .main-title {
        background: linear-gradient(135deg, #1b9e77 0%, #028090 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        font-size: 2.8rem;
        margin-bottom: 0.2rem;
    }
    
    .subtitle {
        color: #555555;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* KPI Card styling */
    .kpi-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 5px solid #1b9e77;
        margin-bottom: 1rem;
        transition: transform 0.2s;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
    }
    .kpi-title {
        font-size: 0.9rem;
        color: #777777;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        color: #2b2d42;
        margin-top: 0.2rem;
    }
    .kpi-desc {
        font-size: 0.8rem;
        color: #999999;
        margin-top: 0.2rem;
    }
    
    /* Tab headers styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 1.1rem;
        font-weight: 600;
        padding: 12px 16px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Define regional mapping for names
REGIONES_MAP = {
    1: "Tarapacá",
    2: "Antofagasta",
    3: "Atacama",
    4: "Coquimbo",
    5: "Valparaíso",
    6: "O'Higgins",
    7: "Maule",
    8: "Bío-Bío",
    9: "La Araucanía",
    10: "Los Lagos",
    11: "Aysén",
    12: "Magallanes",
    13: "Metropolitana",
    14: "Los Ríos",
    15: "Arica y Parinacota",
    16: "Ñuble"
}

# Age ranges mappings
AGE_MAP = {
    0: "0-4",
    5: "5-9",
    10: "10-14",
    15: "15-19",
    20: "20-24",
    25: "25-29",
    30: "30-34",
    35: "35-39",
    40: "40-44",
    45: "45-49",
    50: "50-54",
    55: "55-59",
    60: "60-64",
    65: "65-69",
    70: "70-74",
    75: "75-79",
    80: "80-84",
    85: "85+"
}

# Load aggregated data
DATA_FILE = "aggregated_data.json"

@st.cache_data
def load_data():
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()

if data is None:
    st.error("❌ Archivo de datos agregados (`aggregated_data.json`) no encontrado.")
    st.info("Por favor, ejecuta primero el script de preprocesamiento `process_data.py` en tu terminal local para generar el archivo de datos consolidado necesario.")
    st.stop()

# Load and Cache GeoJSON for Chile
@st.cache_data
def get_geojson():
    GEOJSON_URL = "https://raw.githubusercontent.com/fcortes/Chile-GeoJSON/master/Regional.geojson"
    try:
        chile_geo = requests.get(GEOJSON_URL).json()
        
        # Filter distant islands to focus on continental Chile (Arica to Punta Arenas)
        def filtrar_islas_lejanas(geojson, lon_min=-76, lon_max=-64, lat_min=-56, lat_max=-17):
            geo = copy.deepcopy(geojson)
            for feat in geo["features"]:
                geom = feat["geometry"]
                if geom["type"] == "MultiPolygon":
                    validos = []
                    for poly in geom["coordinates"]:
                        lons = [c[0] for ring in poly for c in ring]
                        lats = [c[1] for ring in poly for c in ring]
                        cx = sum(lons) / len(lons)
                        cy = sum(lats) / len(lats)
                        if lon_min <= cx <= lon_max and lat_min <= cy <= lat_max:
                            validos.append(poly)
                    geom["coordinates"] = validos if validos else geom["coordinates"][:1]
            return geo
        
        return filtrar_islas_lejanas(chile_geo)
    except Exception as e:
        st.error(f"Error cargando el mapa de Chile: {e}")
        return None

chile_geo_filtrado = get_geojson()

# Sidebar Filters
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/a/a1/Logo_del_INE_Chile.svg", width=120)
st.sidebar.title("Filtros del Dashboard")
st.sidebar.write("Ajusta los parámetros para explorar los datos interactivos a nivel nacional o regional.")

# Region Filter
regiones_options = ["Todas"] + [f"{k}: {v}" for k, v in sorted(REGIONES_MAP.items())]
region_sel = st.sidebar.selectbox("Seleccione Región", options=regiones_options, index=0)

if region_sel == "Todas":
    selected_region_id = None
else:
    selected_region_id = int(region_sel.split(":")[0])

# Area Filter (Urbano/Rural)
area_sel = st.sidebar.multiselect(
    "Área Geográfica",
    options=["Urbano", "Rural"],
    default=["Urbano", "Rural"]
)

# Professional condition label mapping helper
prof_desc_map = {1: "Profesional", 0: "No Profesional"}

# Map of area code to name
area_code_map = {1: "Urbano", 2: "Rural"}

# Title Section
st.markdown("<h1 class='main-title'>Dashboard Censo 2024</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Visualización interactiva de la tenencia de vivienda propia y brechas digitales por condición profesional</p>", unsafe_allow_html=True)

# Data Filtering Logic based on user selection
# 1. Housing counts (for Sunburst/Treemap)
df_housing = pd.DataFrame(data["housing_counts"])
df_housing["area_name"] = df_housing["area"].map(area_code_map)
df_housing["Estado"] = df_housing["p12_tenencia_viv"].map({1: "Pagada", 2: "Pagándose"})

if selected_region_id is not None:
    df_housing = df_housing[df_housing["region"] == selected_region_id]
df_housing = df_housing[df_housing["area_name"].isin(area_sel)]

# Calculate KPIs
total_viviendas_filtered = df_housing["Cantidad"].sum()
viviendas_pagadas = df_housing[df_housing["p12_tenencia_viv"] == 1]["Cantidad"].sum()
pct_propiedad_pagada = (viviendas_pagadas / total_viviendas_filtered * 100) if total_viviendas_filtered > 0 else 0

# Brecha Nacional (KPI)
df_pct_pagada_full = pd.DataFrame(data["pct_pagada"])
if selected_region_id is not None:
    df_pct_pagada_full = df_pct_pagada_full[df_pct_pagada_full["region"] == selected_region_id]
    
pct_prof_total = df_pct_pagada_full[df_pct_pagada_full["profesional"] == 1]
pct_noprof_total = df_pct_pagada_full[df_pct_pagada_full["profesional"] == 0]

pct_prof_rate = (pct_prof_total["is_pagada_sum"].sum() / pct_prof_total["count"].sum() * 100) if pct_prof_total["count"].sum() > 0 else 0
pct_noprof_rate = (pct_noprof_total["is_pagada_sum"].sum() / pct_noprof_total["count"].sum() * 100) if pct_noprof_total["count"].sum() > 0 else 0
brecha_nacional = pct_prof_rate - pct_noprof_rate

# KPI Cards layout
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div class="kpi-card" style="border-left-color: #1b9e77;">
        <div class="kpi-title">Viviendas Propias Analizadas</div>
        <div class="kpi-value">{total_viviendas_filtered:,.0f}</div>
        <div class="kpi-desc">Total viviendas propias en la selección</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="kpi-card" style="border-left-color: #028090;">
        <div class="kpi-title">Tasa de Propiedad Pagada</div>
        <div class="kpi-value">{pct_propiedad_pagada:.1f}%</div>
        <div class="kpi-desc">Viviendas propias que ya están pagadas</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="kpi-card" style="border-left-color: #e7298a;">
        <div class="kpi-title">Brecha Profesional/No Profesional</div>
        <div class="kpi-value">{brecha_nacional:+.1f} pp</div>
        <div class="kpi-desc">% Vivienda pagada (Prof. − No Prof.)</div>
    </div>
    """, unsafe_allow_html=True)

# Tabs definitions
tab1, tab2, tab3 = st.tabs([
    "🏠 Tenencia de Vivienda",
    "💻 Acceso Tecnológico",
    "🗺️ Distribución Territorial"
])

# -------------------------------------------------------------
# TAB 1: TENENCIA DE VIVIENDA
# -------------------------------------------------------------
with tab1:
    st.subheader("Análisis de Tenencia y Jerarquías de Vivienda")
    st.write("Explora cómo se distribuyen las viviendas según el área geográfica, tipo y estado de pago.")
    
    col_left, col_right = st.columns(2)
    
    # 1. Sunburst: Jerarquía por Área y Estado
    with col_left:
        st.markdown("### Jerarquía de Vivienda Propia: Área y Estado")
        
        piyg_palette = px.colors.diverging.PiYG
        
        # Aggregate counts for Sunburst
        dist_full = df_housing.groupby(["area_name", "Estado"])["Cantidad"].sum().reset_index()
        
        labels, parents, ids, values, colors = [], [], [], [], []
        # Nivel 1: Areas
        for area in ["Urbano", "Rural"]:
            sub = dist_full[dist_full["area_name"] == area]
            total = sub["Cantidad"].sum()
            if total > 0:
                labels.append(area)
                parents.append("")
                ids.append(area)
                values.append(total)
                colors.append(piyg_palette[0] if area == "Urbano" else piyg_palette[-1])
                
                # Nivel 2: Estado
                for _, row in sub.iterrows():
                    labels.append(row["Estado"])
                    parents.append(area)
                    ids.append(f"{area}-{row['Estado']}")
                    values.append(row["Cantidad"])
                    if area == "Urbano":
                        colors.append(piyg_palette[1] if row["Estado"] == "Pagada" else piyg_palette[3])
                    else:
                        colors.append(piyg_palette[-2] if row["Estado"] == "Pagada" else piyg_palette[-4])
        
        if len(ids) > 0:
            fig_sun = go.Figure(
                go.Sunburst(
                    ids=ids,
                    labels=labels,
                    parents=parents,
                    values=values,
                    branchvalues="total",
                    marker=dict(colors=colors, line=dict(color="white", width=2)),
                    textinfo="label+percent parent",
                    insidetextorientation="radial",
                    textfont=dict(size=13),
                )
            )
            fig_sun.update_layout(
                height=500,
                margin=dict(t=20, l=10, r=10, b=10),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_sun, use_container_width=True)
        else:
            st.warning("No hay datos disponibles para la combinación de filtros seleccionada.")

    # 2. Treemap: Área, Tipo y Estado
    with col_right:
        st.markdown("### Estructura de Proporciones (Área -> Tipo -> Estado)")
        
        # Map p2_tipo_vivienda to names (Casa = 1, Departamento = 3)
        df_tree_data = df_housing[df_housing["p2_tipo_vivienda"].isin([1, 3])].copy()
        df_tree_data["tipo_viv_name"] = df_tree_data["p2_tipo_vivienda"].map({1: "Casa", 3: "Departamento"})
        
        df_tree = df_tree_data.groupby(["area_name", "tipo_viv_name", "Estado"])["Cantidad"].sum().reset_index()
        
        labels_t, parents_t, ids_t, values_t, colors_t = [], [], [], [], []
        
        # Nivel 1: Área
        for area in ["Urbano", "Rural"]:
            u_total = df_tree[df_tree["area_name"] == area]["Cantidad"].sum()
            if u_total > 0:
                labels_t.append(area)
                parents_t.append("")
                ids_t.append(area)
                values_t.append(u_total)
                colors_t.append(piyg_palette[0] if area == "Urbano" else piyg_palette[-1])
                
                # Nivel 2: Tipo
                for tipo in ["Casa", "Departamento"]:
                    sub_total = df_tree[(df_tree["area_name"] == area) & (df_tree["tipo_viv_name"] == tipo)]["Cantidad"].sum()
                    if sub_total > 0:
                        labels_t.append(tipo)
                        parents_t.append(area)
                        ids_t.append(f"{area}/{tipo}")
                        values_t.append(sub_total)
                        colors_t.append(piyg_palette[1] if area == "Urbano" else piyg_palette[-2])
                        
                        # Nivel 3: Estado
                        for _, row in df_tree[(df_tree["area_name"] == area) & (df_tree["tipo_viv_name"] == tipo)].iterrows():
                            labels_t.append(row["Estado"])
                            parents_t.append(f"{area}/{tipo}")
                            ids_t.append(f"{area}/{tipo}/{row['Estado']}")
                            values_t.append(row["Cantidad"])
                            if area == "Urbano":
                                colors_t.append(piyg_palette[2] if row["Estado"] == "Pagada" else piyg_palette[4])
                            else:
                                colors_t.append(piyg_palette[-3] if row["Estado"] == "Pagada" else piyg_palette[-5])
                                
        if len(ids_t) > 0:
            fig_tree = go.Figure(
                go.Treemap(
                    ids=ids_t,
                    labels=labels_t,
                    parents=parents_t,
                    values=values_t,
                    branchvalues="total",
                    marker=dict(colors=colors_t),
                    texttemplate="%{label} %{percentParent:.0%}<br>%{value:,.0f}",
                    textfont=dict(size=12)
                )
            )
            fig_tree.update_layout(
                height=500,
                margin=dict(t=20, l=10, r=10, b=10),
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_tree, use_container_width=True)
        else:
            st.warning("No hay datos disponibles para la combinación de filtros.")

    st.markdown("---")
    
    col_bottom_left, col_bottom_right = st.columns(2)
    
    # 3. Probability by Cycle of Life (Age and Professional Status)
    with col_bottom_left:
        st.markdown("### Probabilidad de Vivienda Pagada por Ciclo de Vida")
        
        df_age = pd.DataFrame(data["age_ownership"])
        if selected_region_id is not None:
            df_age = df_age[df_age["region"] == selected_region_id]
            
        # Group by age and professional
        age_grouped = df_age.groupby(["edad_quinquenal", "profesional"]).agg(
            is_pagada_sum=("is_pagada_sum", "sum"),
            count=("count", "sum")
        ).reset_index()
        
        # Map Numeric age_quinquenal to String range
        age_grouped["edad_quinquenal_str"] = age_grouped["edad_quinquenal"].map(AGE_MAP)
        age_grouped["Porcentaje Pagada"] = age_grouped["is_pagada_sum"] / age_grouped["count"] * 100
        age_grouped["Condición profesional"] = age_grouped["profesional"].map(prof_desc_map)
        
        # Sort values chronologically
        orden_edades = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85+"]
        age_grouped["edad_quinquenal_cat"] = pd.Categorical(age_grouped["edad_quinquenal_str"], categories=orden_edades, ordered=True)
        age_grouped = age_grouped.sort_values("edad_quinquenal_cat").dropna(subset=["edad_quinquenal_cat"])
        
        fig_prob = px.line(
            age_grouped,
            x="edad_quinquenal_cat",
            y="Porcentaje Pagada",
            color="Condición profesional",
            markers=True,
            color_discrete_map={"Profesional": "#1b9e77", "No Profesional": "#e7298a"},
            labels={"edad_quinquenal_cat": "Tramo de Edad", "Porcentaje Pagada": "% Vivienda Propia Pagada"}
        )
        fig_prob.update_layout(
            template="simple_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(ticksuffix="%"),
            height=400,
            margin=dict(t=20, l=10, r=10, b=10)
        )
        st.plotly_chart(fig_prob, use_container_width=True)
        
    # 4. Stacked Bar Chart: Tenencia por Condición Profesional
    with col_bottom_right:
        st.markdown("### Distribución de Tenencia según Condición Profesional")
        
        df_ten = pd.DataFrame(data["tenencia"])
        if selected_region_id is not None:
            df_ten = df_ten[df_ten["region"] == selected_region_id]
            
        ten_grouped = df_ten.groupby(["profesional", "tenencia_simple"])["count"].sum().reset_index()
        
        # Calculate percentage inside each group
        ten_grouped["Porcentaje"] = ten_grouped.groupby("profesional")["count"].transform(lambda x: x / x.sum() * 100)
        ten_grouped["Condición profesional"] = ten_grouped["profesional"].map(prof_desc_map)
        
        orden_tenencia = ["Propia pagada", "No propia", "Otro"]
        ten_grouped["Tenencia de la vivienda"] = pd.Categorical(ten_grouped["tenencia_simple"], categories=orden_tenencia, ordered=True)
        ten_grouped = ten_grouped.sort_values("Tenencia de la vivienda")
        
        fig_ten_bar = px.bar(
            ten_grouped,
            x="Condición profesional",
            y="Porcentaje",
            color="Tenencia de la vivienda",
            color_discrete_map={
                "Propia pagada": "#F8766D",
                "No propia": "#C77CFF",
                "Otro": "#BDBDBD"
            },
            barmode="stack",
            labels={"Porcentaje": "Porcentaje (%)", "Condición profesional": "Condición Profesional"}
        )
        fig_ten_bar.update_layout(
            template="simple_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(ticksuffix="%"),
            height=400,
            margin=dict(t=20, l=10, r=10, b=10)
        )
        st.plotly_chart(fig_ten_bar, use_container_width=True)

# -------------------------------------------------------------
# TAB 2: ACCESO TECNOLÓGICO Y CONECTIVIDAD
# -------------------------------------------------------------
with tab2:
    st.subheader("Acceso a Tecnologías y Conectividad")
    st.write("Analiza las brechas digitales y de conectividad según tramos de edad y condición profesional.")
    
    col_tech_left, col_tech_right = st.columns(2)
    
    # 5. Radar Chart: Tech access proportions
    with col_tech_left:
        st.markdown("### Acceso a Tecnologías Digitales (Perfil General)")
        
        df_rad = pd.DataFrame(data["radar"])
        if selected_region_id is not None:
            df_rad = df_rad[df_rad["region"] == selected_region_id]
            
        rad_grouped = df_rad.groupby("profesional").sum().reset_index()
        
        SERVICIOS_MAP = {
            "tel_movil_sum": "Tel. Móvil",
            "compu_sum": "Computador",
            "tablet_sum": "Tablet",
            "internet_fija_sum": "Internet Fija",
            "internet_movil_sum": "Internet Móvil"
        }
        
        radar_list = []
        for col_name, s_label in SERVICIOS_MAP.items():
            for prof in [1, 0]:
                sub_row = rad_grouped[rad_grouped["profesional"] == prof]
                if not sub_row.empty:
                    acc_val = (sub_row[col_name].values[0] / sub_row["count"].values[0] * 100)
                else:
                    acc_val = 0
                radar_list.append({
                    "Servicio": s_label,
                    "Condición": prof_desc_map[prof],
                    "Acceso": acc_val
                })
        
        df_radar_plot = pd.DataFrame(radar_list)
        
        fig_radar = px.line_polar(
            df_radar_plot,
            r="Acceso",
            theta="Servicio",
            color="Condición",
            line_close=True,
            markers=True,
            color_discrete_map={"Profesional": "#1b9e77", "No Profesional": "#e7298a"}
        )
        fig_radar.update_traces(fill="toself", opacity=0.4)
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    ticksuffix="%",
                    gridcolor="lightgray",
                    tickfont=dict(size=11)
                ),
                angularaxis=dict(
                    gridcolor="lightgray",
                    tickfont=dict(size=12, color="black")
                )
            ),
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
            height=450,
            margin=dict(t=20, l=40, r=40, b=40)
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # 6. Line Plot: Internet Access (acceso_internet) by Age/Prof
    with col_tech_right:
        st.markdown("### Acceso a Internet por Edad y Condición Profesional")
        
        df_int = pd.DataFrame(data["internet"])
        if selected_region_id is not None:
            df_int = df_int[df_int["region"] == selected_region_id]
            
        int_grouped = df_int.groupby(["edad_quinquenal", "profesional"]).sum().reset_index()
        int_grouped["edad_quinquenal_str"] = int_grouped["edad_quinquenal"].map(AGE_MAP)
        int_grouped["Acceso a Internet"] = int_grouped["internet_sum"] / int_grouped["count"]
        int_grouped["Condición profesional"] = int_grouped["profesional"].map(prof_desc_map)
        
        orden_edades = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85+"]
        int_grouped["edad_quinquenal_cat"] = pd.Categorical(int_grouped["edad_quinquenal_str"], categories=orden_edades, ordered=True)
        int_grouped = int_grouped.sort_values("edad_quinquenal_cat").dropna(subset=["edad_quinquenal_cat"])
        
        fig_int_line = px.line(
            int_grouped,
            x="edad_quinquenal_cat",
            y="Acceso a Internet",
            color="Condición profesional",
            markers=True,
            color_discrete_map={"Profesional": "#1b9e77", "No Profesional": "#e7298a"},
            labels={"edad_quinquenal_cat": "Tramo de Edad", "Acceso a Internet": "Tasa de Acceso (%)"}
        )
        fig_int_line.update_layout(
            template="simple_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(range=[0, 1.05], tickformat=".0%"),
            height=400,
            margin=dict(t=20, l=10, r=10, b=10)
        )
        st.plotly_chart(fig_int_line, use_container_width=True)

    st.markdown("---")
    
    col_tech_bot_left, col_tech_bot_right = st.columns(2)
    
    # 7. Line Plot: All services by age and professional status
    with col_tech_bot_left:
        st.markdown("### Acceso Detallado a Tecnologías por Edad")
        
        df_t = pd.DataFrame(data["tech"])
        if selected_region_id is not None:
            df_t = df_t[df_t["region"] == selected_region_id]
            
        t_grouped = df_t.groupby(["edad_quinquenal", "profesional"]).sum().reset_index()
        
        services_detail = {
            "tel_movil_sum": "Teléfono móvil",
            "compu_sum": "Computador",
            "tablet_sum": "Tablet",
            "internet_fija_sum": "Internet fija",
            "internet_movil_sum": "Internet móvil",
            "internet_satelital_sum": "Internet satelital"
        }
        
        t_list = []
        for col_name, s_name in services_detail.items():
            for (eq, prof), gdf in t_grouped.groupby(["edad_quinquenal", "profesional"]):
                rate = gdf[col_name].values[0] / gdf["count"].values[0] if gdf["count"].values[0] > 0 else 0
                t_list.append({
                    "edad_quinquenal_val": eq,
                    "profesional_desc": prof_desc_map[prof],
                    "Acceso": rate,
                    "Servicio": s_name
                })
        df_tech_detail = pd.DataFrame(t_list)
        df_tech_detail["edad_quinquenal_str"] = df_tech_detail["edad_quinquenal_val"].map(AGE_MAP)
        
        orden_edades = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85+"]
        df_tech_detail["edad_quinquenal_cat"] = pd.Categorical(df_tech_detail["edad_quinquenal_str"], categories=orden_edades, ordered=True)
        df_tech_detail = df_tech_detail.sort_values("edad_quinquenal_cat").dropna(subset=["edad_quinquenal_cat"])
        
        fig_tech_detail = px.line(
            df_tech_detail,
            x="edad_quinquenal_cat",
            y="Acceso",
            color="Servicio",
            line_dash="profesional_desc",
            markers=True,
            labels={"edad_quinquenal_cat": "Tramo de Edad", "Acceso": "Tasa de Acceso (%)"}
        )
        fig_tech_detail.update_layout(
            template="simple_white",
            yaxis=dict(range=[0, 1.05], tickformat=".0%"),
            height=450,
            margin=dict(t=20, l=10, r=10, b=10),
            legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_tech_detail, use_container_width=True)

    # 8. Line Plot: Selected technologies (Mobile, Computer, Mobile internet) (15+ years)
    with col_tech_bot_right:
        st.markdown("### Acceso a Tecnologías Seleccionadas (15+ años)")
        
        # We filter for age >= 15
        df_tech_sel = df_tech_detail[
            df_tech_detail["Servicio"].isin(["Teléfono móvil", "Computador", "Internet móvil"])
        ].copy()
        
        line_dash_map = {
            "Profesional": "solid",
            "No Profesional": "dot"
        }
        
        fig_tech_sel = px.line(
            df_tech_sel,
            x="edad_quinquenal_cat",
            y="Acceso",
            color="Servicio",
            line_dash="profesional_desc",
            line_dash_map=line_dash_map,
            markers=True,
            labels={"edad_quinquenal_cat": "Tramo de Edad (desde 15 años)", "Acceso": "Tasa de Acceso (%)"}
        )
        fig_tech_sel.update_layout(
            template="simple_white",
            yaxis=dict(range=[0, 1.05], tickformat=".0%"),
            height=450,
            margin=dict(t=20, l=10, r=10, b=10),
            legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_tech_sel, use_container_width=True)

# -------------------------------------------------------------
# TAB 3: ANÁLISIS GEOGRÁFICO Y LISA
# -------------------------------------------------------------
with tab3:
    st.subheader("Análisis Espacial y Territorial de Brechas")
    st.write("Visualiza la brecha en vivienda propia pagada a lo largo del territorio nacional y analiza los agrupamientos espaciales significativos.")
    
    if chile_geo_filtrado is None:
        st.error("No se pudo cargar el mapa base de Chile. Por favor verifica tu conexión a internet.")
    else:
        # Build spatial brecha dataset
        df_pct = pd.DataFrame(data["pct_pagada"])
        
        # Pivot and flatten MultiIndex robustly
        brecha_map = df_pct.pivot(index="region", columns="profesional", values=["is_pagada_sum", "count"])
        brecha_map.columns = [f"{val}_{col}" for val, col in brecha_map.columns]
        brecha_map = brecha_map.reset_index()
        
        # Rename columns to standard names
        brecha_map = brecha_map.rename(columns={
            "is_pagada_sum_0": "noprof_sum",
            "is_pagada_sum_1": "prof_sum",
            "count_0": "noprof_count",
            "count_1": "prof_count"
        })
        
        brecha_map["Profesional"] = brecha_map["prof_sum"] / brecha_map["prof_count"] * 100
        brecha_map["No Profesional"] = brecha_map["noprof_sum"] / brecha_map["noprof_count"] * 100
        brecha_map["Brecha (p.p.)"] = brecha_map["Profesional"] - brecha_map["No Profesional"]
        
        # Add Region Name from GeoJSON
        nombres_geo = {
            f["properties"]["codregion"]: f["properties"]["Region"]
            for f in chile_geo_filtrado["features"]
        }
        brecha_map["Región"] = brecha_map["region"].map(nombres_geo)
        
        # Add LISA cluster static results
        df_lisa_static = pd.DataFrame(data["lisa"])
        brecha_map = brecha_map.merge(df_lisa_static[["region", "cluster_lisa"]], on="region", how="left")
        
        col_map1, col_map2 = st.columns(2)
        
        with col_map1:
            st.markdown("### Brecha Espacial en Vivienda Propia Pagada")
            st.write("Muestra la diferencia porcentual entre Profesionales y No Profesionales (Adultos ≥ 18 años).")
            
            fig_map = px.choropleth(
                brecha_map,
                geojson=chile_geo_filtrado,
                locations="region",
                featureidkey="properties.codregion",
                color="Brecha (p.p.)",
                color_continuous_scale=px.colors.diverging.PiYG,
                color_continuous_midpoint=0,
                hover_name="Región",
                hover_data={
                    "Profesional": ":.1f",
                    "No Profesional": ":.1f",
                    "Brecha (p.p.)": ":.1f",
                    "region": False,
                },
                labels={
                    "Profesional": "% Prof. c/ viv. pagada",
                    "No Profesional": "% No Prof. c/ viv. pagada",
                }
            )
            
            fig_map.update_geos(
                visible=False,
                lataxis_range=[-56, -17],
                lonaxis_range=[-76, -64],
            )
            fig_map.update_layout(
                height=700,
                margin=dict(l=0, r=0, t=20, b=0),
                coloraxis_colorbar=dict(
                    title="Brecha<br>(p.p.)",
                    thickness=15,
                    len=0.7,
                    ticksuffix=" pp",
                )
            )
            st.plotly_chart(fig_map, use_container_width=True)
            
        with col_map2:
            st.markdown("### Agrupamiento Espacial (LISA) de la Brecha")
            st.write("Identificación de patrones espaciales y regiones atípicas significativas (Moran Local).")
            
            colores_lisa = {
                "Alto-Alto": "#b2182b",
                "Bajo-Bajo": "#2166ac",
                "Alto-Bajo": "#ef8a62",
                "Bajo-Alto": "#67a9cf",
                "No significativo": "#d9d9d9",
            }
            
            fig_lisa = px.choropleth(
                brecha_map,
                geojson=chile_geo_filtrado,
                locations="region",
                featureidkey="properties.codregion",
                color="cluster_lisa",
                color_discrete_map=colores_lisa,
                hover_name="Región",
                hover_data={
                    "Brecha (p.p.)": ":.1f",
                    "cluster_lisa": True,
                    "region": False,
                },
                labels={
                    "cluster_lisa": "Clasificación LISA",
                    "Brecha (p.p.)": "Brecha (p.p.)"
                }
            )
            
            fig_lisa.update_geos(
                visible=False,
                lataxis_range=[-56, -17],
                lonaxis_range=[-76, -64],
            )
            fig_lisa.update_layout(
                height=700,
                margin=dict(l=0, r=0, t=20, b=0),
                legend=dict(
                    title="Clasificación LISA",
                    orientation="v",
                    yanchor="top",
                    y=0.9,
                    xanchor="left",
                    x=0.02,
                    bordercolor="gray",
                    borderwidth=1,
                    bgcolor="white"
                )
            )
            st.plotly_chart(fig_lisa, use_container_width=True)

# Footer credits
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #777777; font-size: 0.9rem; margin-top: 1rem; margin-bottom: 2rem;'>"
    "Dashboard Creado para la Entrega 3 de Data Visualization · Datos del Censo de Población y Vivienda 2024 (INE Chile)"
    "</div>",
    unsafe_allow_html=True
)
