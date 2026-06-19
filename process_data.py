import pandas as pd
import numpy as np
import json
import os
import sys

# Set stdout encoding to UTF-8 to prevent console errors
sys.stdout.reconfigure(encoding='utf-8')

# Input paths in the workspace
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
viviendas_path = os.path.join(BASE_DIR, "viviendas_censo2024.csv")
hogares_path = os.path.join(BASE_DIR, "hogares_censo2024.csv")
personas_path = os.path.join(BASE_DIR, "personas_censo2024.csv")

print("🔍 Iniciando preprocesamiento de datos del Censo 2024...")
print(f"Buscando archivos en: {BASE_DIR}")

# Check that files exist
for p in [viviendas_path, hogares_path, personas_path]:
    if not os.path.exists(p):
        print(f"❌ Error: No se encontró el archivo {p}")
        sys.exit(1)

print("📖 Cargando base de viviendas...")
df_viv = pd.read_csv(viviendas_path, sep=";", usecols=["id_vivienda", "region", "area", "p2_tipo_vivienda"], encoding="latin-1")

print("📖 Cargando base de hogares...")
df_hog = pd.read_csv(hogares_path, sep=";", usecols=[
    "id_vivienda", "id_hogar", "p12_tenencia_viv",
    "p15a_serv_tel_movil", "p15b_serv_compu", "p15c_serv_tablet",
    "p15d_serv_internet_fija", "p15e_serv_internet_movil", "p15f_serv_internet_satelital"
], encoding="latin-1")

print("🔄 Realizando unión viviendas-hogares...")
df_hog_viv = df_hog.merge(df_viv, on="id_vivienda", how="left")

# 1. Sunburst / Treemap Data (Vivienda level)
print("📊 Pre-calculando conteos de vivienda propia (Nivel Vivienda)...")
df_housing_owned = df_hog_viv[df_hog_viv["p12_tenencia_viv"].isin([1, 2])].copy()
df_housing_uniq = df_housing_owned.drop_duplicates("id_vivienda")
housing_counts = df_housing_uniq.groupby(["region", "area", "p2_tipo_vivienda", "p12_tenencia_viv"]).size().reset_index(name="Cantidad")

# Initialize list aggregators for streaming personas
age_ownership_acc = []
tenencia_acc = []
radar_acc = []
pct_pagada_acc = []
internet_acc = []
tech_acc = []

seen_viviendas_owned = set()

# Columns to load from personas (2.5 GB)
cols_pers = ["id_vivienda", "id_hogar", "edad", "edad_quinquenal", "parentesco", "cine11"]

print("⏳ Procesando base de personas en bloques de 1,000,000 de filas...")
chunk_size = 1000000
chunk_idx = 0

for chunk in pd.read_csv(personas_path, sep=";", usecols=cols_pers, chunksize=chunk_size, encoding="latin-1"):
    chunk_idx += 1
    print(f"   Procesando bloque {chunk_idx}...", end="\r")
    
    # Filter valid age
    chunk = chunk[chunk["edad"] >= 0].copy()
    if chunk.empty:
        continue
        
    # Merge with housing variables
    m_chunk = chunk.merge(df_hog_viv, on=["id_vivienda", "id_hogar"], how="left")
    if m_chunk.empty:
        continue
        
    # Create derived features
    m_chunk["profesional"] = m_chunk["cine11"].isin([8, 9, 10, 11]).astype(int)
    m_chunk["is_pagada"] = (m_chunk["p12_tenencia_viv"] == 1).astype(int)
    
    # Tenencia simple mapping
    mapa_tenencia = {
        1: "Propia pagada",
        2: "No propia",
        3: "No propia",
        4: "No propia",
        5: "Otro", 6: "Otro", 7: "Otro", 8: "Otro", 9: "Otro", -99: "Otro"
    }
    m_chunk["tenencia_simple"] = m_chunk["p12_tenencia_viv"].map(mapa_tenencia).fillna("Otro")
    
    # Acceso internet
    m_chunk["acceso_internet"] = (
        (m_chunk["p15d_serv_internet_fija"] == 1) |
        (m_chunk["p15e_serv_internet_movil"] == 1) |
        (m_chunk["p15f_serv_internet_satelital"] == 1)
    ).astype(int)
    
    # A. Probabilidad por tramo edad (Viviendas Propias, única por vivienda)
    owned_chunk = m_chunk[m_chunk["p12_tenencia_viv"].isin([1, 2])].copy()
    if not owned_chunk.empty:
        owned_chunk = owned_chunk[~owned_chunk["id_vivienda"].isin(seen_viviendas_owned)]
        seen_viviendas_owned.update(owned_chunk["id_vivienda"])
        if not owned_chunk.empty:
            gp = owned_chunk.groupby(["region", "edad_quinquenal", "profesional"]).agg(
                is_pagada_sum=("is_pagada", "sum"),
                count=("id_vivienda", "count")
            ).reset_index()
            age_ownership_acc.append(gp)
            
    # B. Tenencia regional (Nivel Persona)
    gp_b = m_chunk.groupby(["region", "profesional", "tenencia_simple"]).size().reset_index(name="count")
    tenencia_acc.append(gp_b)
    
    # C. Radar de tecnologías (Nivel Persona)
    gp_c = m_chunk.groupby(["region", "profesional"]).agg(
        count=("id_vivienda", "count"),
        tel_movil_sum=("p15a_serv_tel_movil", lambda x: (x == 1).sum()),
        compu_sum=("p15b_serv_compu", lambda x: (x == 1).sum()),
        tablet_sum=("p15c_serv_tablet", lambda x: (x == 1).sum()),
        internet_fija_sum=("p15d_serv_internet_fija", lambda x: (x == 1).sum()),
        internet_movil_sum=("p15e_serv_internet_movil", lambda x: (x == 1).sum())
    ).reset_index()
    radar_acc.append(gp_c)
    
    # D. Tasa pagada regional para brecha (Adultos >= 18)
    adults_chunk = m_chunk[m_chunk["edad"] >= 18]
    if not adults_chunk.empty:
        gp_d = adults_chunk.groupby(["region", "profesional"]).agg(
            is_pagada_sum=("is_pagada", "sum"),
            count=("id_vivienda", "count")
        ).reset_index()
        pct_pagada_acc.append(gp_d)
        
    # E. Acceso a internet por edad/profesional (Nivel Persona)
    gp_e = m_chunk.groupby(["region", "edad_quinquenal", "profesional"]).agg(
        internet_sum=("acceso_internet", "sum"),
        count=("id_vivienda", "count")
    ).reset_index()
    internet_acc.append(gp_e)
    
    # F. Detalle de tecnologías por edad/profesional (Nivel Persona)
    gp_f = m_chunk.groupby(["region", "edad_quinquenal", "profesional"]).agg(
        count=("id_vivienda", "count"),
        tel_movil_sum=("p15a_serv_tel_movil", lambda x: (x == 1).sum()),
        compu_sum=("p15b_serv_compu", lambda x: (x == 1).sum()),
        tablet_sum=("p15c_serv_tablet", lambda x: (x == 1).sum()),
        internet_fija_sum=("p15d_serv_internet_fija", lambda x: (x == 1).sum()),
        internet_movil_sum=("p15e_serv_internet_movil", lambda x: (x == 1).sum()),
        internet_satelital_sum=("p15f_serv_internet_satelital", lambda x: (x == 1).sum())
    ).reset_index()
    tech_acc.append(gp_f)

print(f"\n✅ Procesamiento de bloques finalizado. Total bloques: {chunk_idx}")

# Combine all lists of dataframes
print("🔄 Consolidando resultados y agrupando...")
df_age_ownership = pd.concat(age_ownership_acc).groupby(["region", "edad_quinquenal", "profesional"]).sum().reset_index()
df_tenencia = pd.concat(tenencia_acc).groupby(["region", "profesional", "tenencia_simple"])["count"].sum().reset_index()
df_radar = pd.concat(radar_acc).groupby(["region", "profesional"]).sum().reset_index()
df_pct_pagada = pd.concat(pct_pagada_acc).groupby(["region", "profesional"]).sum().reset_index()
df_internet = pd.concat(internet_acc).groupby(["region", "edad_quinquenal", "profesional"]).sum().reset_index()
df_tech = pd.concat(tech_acc).groupby(["region", "edad_quinquenal", "profesional"]).sum().reset_index()

# Static LISA clusters pre-computed in notebook cell 20
lisa_static = [
    {"region": 15, "region_name": "Región de Arica y Parinacota", "cluster_lisa": "Alto-Alto"},
    {"region": 1, "region_name": "Región de Tarapacá", "cluster_lisa": "Alto-Alto"},
    {"region": 2, "region_name": "Región de Antofagasta", "cluster_lisa": "Alto-Alto"},
    {"region": 12, "region_name": "Región de Magallanes y Antártica Chilena", "cluster_lisa": "Bajo-Bajo"},
    {"region": 11, "region_name": "Región de Aysén del Gral.Ibañez del Campo", "cluster_lisa": "Bajo-Bajo"},
    {"region": 3, "region_name": "Región de Atacama", "cluster_lisa": "No significativo"},
    {"region": 4, "region_name": "Región de Coquimbo", "cluster_lisa": "No significativo"},
    {"region": 5, "region_name": "Región de Valparaíso", "cluster_lisa": "No significativo"},
    {"region": 13, "region_name": "Región Metropolitana de Santiago", "cluster_lisa": "No significativo"},
    {"region": 10, "region_name": "Región de Los Lagos", "cluster_lisa": "Bajo-Bajo"},
    {"region": 14, "region_name": "Región de Los Ríos", "cluster_lisa": "No significativo"},
    {"region": 9, "region_name": "Región de La Araucanía", "cluster_lisa": "No significativo"},
    {"region": 8, "region_name": "Región del Bío-Bío", "cluster_lisa": "No significativo"},
    {"region": 16, "region_name": "Región de Ñuble", "cluster_lisa": "No significativo"},
    {"region": 7, "region_name": "Región del Maule", "cluster_lisa": "No significativo"},
    {"region": 6, "region_name": "Región del Libertador Bernardo O'Higgins", "cluster_lisa": "No significativo"}
]
df_lisa = pd.DataFrame(lisa_static)

# --- Casen history data (pre-computed and verified from the notebook) ---
casen_history = [
    {"año": 2006, "Condición": "No Profesional", "Porcentaje Pagada": 59.399803},
    {"año": 2006, "Condición": "Profesional", "Porcentaje Pagada": 40.183918},
    {"año": 2009, "Condición": "No Profesional", "Porcentaje Pagada": 59.657093},
    {"año": 2009, "Condición": "Profesional", "Porcentaje Pagada": 42.167283},
    {"año": 2011, "Condición": "No Profesional", "Porcentaje Pagada": 80.806220},
    {"año": 2011, "Condición": "Profesional", "Porcentaje Pagada": 74.837512},
    {"año": 2013, "Condición": "No Profesional", "Porcentaje Pagada": 66.419785},
    {"año": 2013, "Condición": "Profesional", "Porcentaje Pagada": 56.388570},
    {"año": 2015, "Condición": "No Profesional", "Porcentaje Pagada": 65.797518},
    {"año": 2015, "Condición": "Profesional", "Porcentaje Pagada": 60.095941},
    {"año": 2017, "Condición": "No Profesional", "Porcentaje Pagada": 57.285561},
    {"año": 2017, "Condición": "Profesional", "Porcentaje Pagada": 35.413217},
    {"año": 2020, "Condición": "No Profesional", "Porcentaje Pagada": 64.570562},
    {"año": 2020, "Condición": "Profesional", "Porcentaje Pagada": 56.666667},
    {"año": 2022, "Condición": "No Profesional", "Porcentaje Pagada": 62.610249},
    {"año": 2022, "Condición": "Profesional", "Porcentaje Pagada": 53.468192},
    {"año": 2024, "Condición": "No Profesional", "Porcentaje Pagada": 61.824125},
    {"año": 2024, "Condición": "Profesional", "Porcentaje Pagada": 52.781086}
]

# --- Pure Python Spatial Autocorrelation Calculation ---
NEIGHBORS = {
    1: [15, 2, 3, 4],
    2: [3, 1, 15, 4],
    3: [4, 2, 5, 13],
    4: [5, 3, 13, 6],
    5: [13, 6, 4, 7],
    6: [13, 7, 5, 16],
    7: [16, 6, 13, 8],
    8: [16, 9, 7, 14],
    9: [8, 14, 16, 7],
    10: [14, 11, 9, 8],
    11: [10, 12, 14, 9],
    12: [11, 10, 14, 9],
    13: [6, 5, 7, 4],
    14: [9, 8, 10, 16],
    15: [1, 2, 3, 4],
    16: [8, 7, 9, 6]
}

# Pivot regional rates to calculate the brecha for each region dynamically
df_pivot = df_pct_pagada.pivot(index="region", columns="profesional", values=["is_pagada_sum", "count"])
df_pivot.columns = [f"{val}_{col}" for val, col in df_pivot.columns]
df_pivot = df_pivot.fillna(0)

# Calculate rates (in percentage)
tasa_prof = df_pivot["is_pagada_sum_1"] / df_pivot["count_1"] * 100
tasa_noprof = df_pivot["is_pagada_sum_0"] / df_pivot["count_0"] * 100
brechas_dict = (tasa_prof - tasa_noprof).to_dict()

# Standardize brechas
regions_sorted = sorted(brechas_dict.keys())
y_vals = np.array([brechas_dict[rid] for rid in regions_sorted])
mean_y = np.mean(y_vals)
std_y = np.std(y_vals)
z_vals = (y_vals - mean_y) / std_y
z_dict = {rid: z_vals[regions_sorted.index(rid)] for rid in regions_sorted}

# Calculate spatial lag of brechas and standardized lag
lag_y_vals = []
z_lag_vals = []
for rid in regions_sorted:
    nbs = NEIGHBORS[rid]
    lag_y_vals.append(float(np.mean([brechas_dict[nb] for nb in nbs])))
    z_lag_vals.append(float(np.mean([z_dict[nb] for nb in nbs])))

# Global Moran's I
moran_i = float(np.sum(z_vals * np.array(z_lag_vals)) / np.sum(z_vals**2))

# Determine quadrants and build records
spatial_correlation = []
for idx, rid in enumerate(regions_sorted):
    zi = float(z_vals[idx])
    zlag_i = z_lag_vals[idx]
    
    if zi >= 0 and zlag_i >= 0:
        quad = "Alto-Alto"
    elif zi < 0 and zlag_i >= 0:
        quad = "Bajo-Alto"
    elif zi < 0 and zlag_i < 0:
        quad = "Bajo-Bajo"
    else:
        quad = "Alto-Bajo"
        
    spatial_correlation.append({
        "region": rid,
        "brecha": float(brechas_dict[rid]),
        "lag_brecha": lag_y_vals[idx],
        "z_brecha": zi,
        "z_lag_brecha": zlag_i,
        "quadrant": quad
    })

# Package all data into a JSON dictionary
output_dict = {
    "housing_counts": housing_counts.to_dict(orient="records"),
    "age_ownership": df_age_ownership.to_dict(orient="records"),
    "tenencia": df_tenencia.to_dict(orient="records"),
    "radar": df_radar.to_dict(orient="records"),
    "pct_pagada": df_pct_pagada.to_dict(orient="records"),
    "internet": df_internet.to_dict(orient="records"),
    "tech": df_tech.to_dict(orient="records"),
    "lisa": df_lisa.to_dict(orient="records"),
    "casen_history": casen_history,
    "spatial_correlation": {
        "moran_i": moran_i,
        "regions_spatial": spatial_correlation
    }
}

output_path = os.path.join(BASE_DIR, "aggregated_data.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output_dict, f, ensure_ascii=False, indent=2)

print(f"🎉 ¡Preprocesamiento completo! Archivo ligero guardado en: {output_path}")
print(f"💾 Tamaño del archivo generado: {os.path.getsize(output_path) / 1024:.2f} KB")

