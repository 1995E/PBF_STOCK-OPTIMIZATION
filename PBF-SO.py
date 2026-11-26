import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import io
import re

# Configure page
st.set_page_config(
    page_title="PBF STOCK ANALYSE TOOL",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATA PREPROCESSING & LOAD ---
@st.cache_data
def load_data():
    # Load datasets
    removed_materials = pd.read_excel('/content/Material Overview per Plant.xlsx')
    unit_prices = pd.read_excel('/content/Material Overview per Price and Valuation Type.xlsx')
    return removed_materials, unit_prices

try:
    removed_materials_df, unit_price_df = load_data()
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# Normalize column names (strip whitespaces, lowercase) to make the code extremely robust
removed_materials_df.columns = removed_materials_df.columns.astype(str).str.strip().str.lower()
unit_price_df.columns = unit_price_df.columns.astype(str).str.strip().str.lower()

# Dynamically find the material number column
mat_col_removed = [col for col in removed_materials_df.columns if 'material' in col or 'mat' in col][0]
mat_col_prices = [col for col in unit_price_df.columns if 'material' in col or 'mat' in col][0]

# Normalize matching key columns to numeric
unit_price_df[mat_col_prices] = pd.to_numeric(unit_price_df[mat_col_prices], errors='coerce')
removed_materials_df[mat_col_removed] = pd.to_numeric(removed_materials_df[mat_col_removed], errors='coerce')

# Use 'item price' lowercase
unit_price_df['unit price'] = pd.to_numeric(unit_price_df['item price'], errors='coerce').fillna(0)
material_prices = unit_price_df.groupby(mat_col_prices)['unit price'].mean()

# Merge to map Unit price back to removed materials
pd_v1_df = removed_materials_df.copy()
pd_v1_df['unit price'] = pd_v1_df[mat_col_removed].map(material_prices)

# Clean FASD status and handle replacement mapping
if 'fasd' in pd_v1_df.columns:
    pd_v1_df['fasd'] = pd_v1_df['fasd'].astype(str).str.strip()
    pd_v1_df['fasd'] = pd_v1_df['fasd'].replace({"Never been consumed": "Dead"})
    pd_v1_df = pd_v1_df[pd_v1_df['fasd'].str.lower() != 'nan']
    pd_v1_df = pd_v1_df[pd_v1_df['fasd'] != '']

# Identify stocked (PD/V1) based on lowercase 'mrp type'
mrp_col = [col for col in pd_v1_df.columns if 'mrp' in col]
if mrp_col:
    pd_v1_df['is_pd_v1'] = pd_v1_df[mrp_col[0]].astype(str).str.strip().str.upper().isin(['PD', 'V1'])
else:
    pd_v1_df['is_pd_v1'] = False

# Add simplified Gest group prefix using case-insensitive check
gest_col = [col for col in pd_v1_df.columns if 'gest' in col]
if gest_col:
    pd_v1_df['gest_2l'] = pd_v1_df[gest_col[0]].astype(str).str.strip().str[:2].str.upper()
else:
    pd_v1_df['gest_2l'] = ''

# App title
st.title("PBF STOCK ANALYSE TOOL")

# Plant segmented control
st.markdown("### Select Plant Filter")
plant_options = ["All", "GIRASSOL", "DALIA", "PAZFLOR", "CLOV"]
plant = st.segmented_control(
    "Filter options:",
    options=plant_options,
    default="All",
    key="plant_selection"
)

# Filter Dataframe for global metrics and charts based on Plant selection
plant_col = [col for col in pd_v1_df.columns if 'plant' in col]
if plant and plant != "All" and plant_col:
    filtered_df = pd_v1_df[pd_v1_df[plant_col[0]].astype(str).str.upper() == plant.upper()]
else:
    filtered_df = pd_v1_df.copy()

# --- METRIC COMPUTATIONS (Responds to Plant selection) ---
Total_removed_materials = filtered_df[mat_col_removed].nunique()
pd_v1_unique_materials = filtered_df[filtered_df['is_pd_v1'] == True]
cnt_pd_v1 = pd_v1_unique_materials[mat_col_removed].nunique()
cnt_nd = max(0, Total_removed_materials - cnt_pd_v1)

# Gest sums
gest_counts_series = pd_v1_unique_materials['gest_2l'].value_counts() if 'gest_2l' in pd_v1_unique_materials.columns else pd.Series(dtype=int)
sum_se = int(gest_counts_series.get('SE', 0))
sum_su = int(gest_counts_series.get('SU', 0))
sum_mm = int(gest_counts_series.get('MM', 0))

# Tab configuration
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Stock overview", "lorepsum 1", "lorepsum 2", "lorepsum 3", "lorepsum 4"])

with tab1:
    col1, col2, col3 = st.columns(3)

    with col1:
        # Toggle option on top
        chart_mode_plant = st.toggle("Show Donut Chart (Plant)", value=False, key="toggle_plant")

        # Process values per plant
        qty_col = [col for col in filtered_df.columns if 'qty' in col or 'quant' in col]
        stock_qty_col = qty_col[0] if qty_col else 'stock qty'
        
        stock_greater_zero = filtered_df[filtered_df[stock_qty_col] > 0].copy() if stock_qty_col in filtered_df.columns else filtered_df.copy()
        stock_greater_zero['Stock Value'] = stock_greater_zero[stock_qty_col] * stock_greater_zero['unit price'].fillna(0) if stock_qty_col in stock_greater_zero.columns else 0
        
        p_col = plant_col[0] if plant_col else 'plant'
        if p_col in stock_greater_zero.columns:
            df_plant_grouped = stock_greater_zero.groupby(p_col)['Stock Value'].sum().reset_index()
        else:
            df_plant_grouped = pd.DataFrame(columns=[p_col, 'Stock Value'])

        if chart_mode_plant:
            # Donut chart
            fig_plant = px.pie(
                df_plant_grouped,
                values='Stock Value',
                names=p_col,
                hole=0.4,
                title="Stock Value Distribution by Plant"
            )
        else:
            # Horizontal bar chart
            fig_plant = px.bar(
                df_plant_grouped,
                x='Stock Value',
                y=p_col,
                orientation='h',
                title="Stock Value by Plant"
            )
        st.plotly_chart(fig_plant, use_container_width=True)

    with col2:
        # Toggle option on top
        chart_mode_fasd = st.toggle("Show Donut Chart (FASD)", value=False, key="toggle_fasd")

        # Process values per FASD status
        stock_greater_zero_fasd = filtered_df[filtered_df[stock_qty_col] > 0].copy() if stock_qty_col in filtered_df.columns else filtered_df.copy()
        stock_greater_zero_fasd['Stock Value'] = stock_greater_zero_fasd[stock_qty_col] * stock_greater_zero_fasd['unit price'].fillna(0) if stock_qty_col in stock_greater_zero_fasd.columns else 0
        
        f_col = 'fasd' if 'fasd' in stock_greater_zero_fasd.columns else None
        if f_col:
            df_fasd_grouped = stock_greater_zero_fasd.groupby(f_col)['Stock Value'].sum().reset_index()
        else:
            df_fasd_grouped = pd.DataFrame(columns=['fasd', 'Stock Value'])

        # Force sorting exact top-to-bottom: Fast, Active, Slow, Dead
        fasd_order = ['Dead', 'Slow', 'Active', 'Fast']

        if chart_mode_fasd:
            # Donut chart
            fig_fasd = px.pie(
                df_fasd_grouped,
                values='Stock Value',
                names='fasd',
                hole=0.4,
                title=f'Stock Value Distribution by FASD Status ({plant if plant else "All"})'
            )
        else:
            # Horizontal bar chart with forced ordering
            fig_fasd = px.bar(
                df_fasd_grouped,
                x='Stock Value',
                y='fasd',
                orientation='h',
                title=f'Stock Value by FASD Status ({plant if plant else "All"})'
            )
            fig_fasd.update_layout(yaxis={'categoryorder': 'array', 'categoryarray': fasd_order})
        st.plotly_chart(fig_fasd, use_container_width=True)

    with col3:
        st.subheader("Material Breakdown Flow")
        st.write(f"**Filtered by:** {plant if plant else 'All'}")
        dot_code = f"""
        digraph G {{
            graph [rankdir=TB, size=\"8,5\", bgcolor=\"transparent\"];
            node [shape=box, style=\"filled,rounded\", color=\"#4B5563\", fillcolor=\"#F3F4F6\", fontname=\"Helvetica\", fontsize=11, fontcolor=\"#1F2937\"];
            edge [color=\"#9CA3AF\", fontname=\"Helvetica\", fontsize=9];
            
            Total [label=\"Total Removed Materials\\n({Total_removed_materials})\", fillcolor=\"#3B82F6\", fontcolor=\"white\"];
            PD_V1 [label=\"Stocked (PD/V1)\\n({cnt_pd_v1})\", fillcolor=\"#10B981\", fontcolor=\"white\"];
            ND [label=\"Non-stocked (ND)\\n({cnt_nd})\", fillcolor=\"#F59E0B\", fontcolor=\"white\"];
            
            SE [label=\"SE Sum\\n({sum_se})\", fillcolor=\"#EC4899\", fontcolor=\"white\"];
            SU [label=\"SU Sum\\n({sum_su})\", fillcolor=\"#8B5CF6\", fontcolor=\"white\"];
            MM [label=\"MM Sum\\n({sum_mm})\", fillcolor=\"#6366F1\", fontcolor=\"white\"];
            
            Total -> PD_V1;
            Total -> ND;
            PD_V1 -> SE;
            PD_V1 -> SU;
            PD_V1 -> MM;
        }}
        """
        st.graphviz_chart(dot_code, use_container_width=True)
