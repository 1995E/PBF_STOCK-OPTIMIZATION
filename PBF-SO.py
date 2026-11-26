import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

# Page config
st.set_page_config(
    page_title="PBF STOCK ANALYSE TOOL",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load Data
@st.cache_data
def load_data():
    removed_df = pd.read_excel('/content/Material Overview per Plant.xlsx')
    price_df = pd.read_excel('/content/Material Overview per Price and Valuation Type.xlsx')
    return removed_df, price_df

try:
    removed_materials_df, unit_price_df = load_data()
    st.success("Data loaded successfully!")
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# Sidebar Filters
st.sidebar.title("Dashboard Filters")

# Plant filter
all_plants = ["All"] + list(removed_materials_df['Plant'].dropna().unique())
selected_plant = st.sidebar.selectbox("Select Plant", options=all_plants)

# Apply Plant Filter
if selected_plant == "All":
    filtered_removed = removed_materials_df
    filtered_price = unit_price_df
else:
    filtered_removed = removed_materials_df[removed_materials_df['Plant'] == selected_plant]
    filtered_price = unit_price_df[unit_price_df['Plant'] == selected_plant]

# Main Dashboard
st.title("PBF Stock Analyse Tool")

# Metrics Calculations based on filtered data
total_materials = len(filtered_removed['Material n°'].unique())

# Dummy classifications/conditions based on dataset structure for the Graphviz graph
# (Adjust the column names if they are named differently in your files)
val_type_col = 'Valuation Type' if 'Valuation Type' in filtered_price.columns else (filtered_price.columns[24] if len(filtered_price.columns) > 24 else filtered_price.columns[-1])
pd_v1_count = len(filtered_price[filtered_price[val_type_col].astype(str).str.contains('PD|V1', case=False, na=False)]['Material n°'].unique())
nd_count = len(filtered_price[filtered_price[val_type_col].astype(str).str.contains('ND', case=False, na=False)]['Material n°'].unique())

# Display overall stats
col1, col2, col3 = st.columns(3)
col1.metric("Total Materials", total_materials)
col2.metric("PD/V1 Materials", pd_v1_count)
col3.metric("ND Materials", nd_count)

# Graphviz Chart with plant filter applied
st.subheader("Material Flow Chart (Filtered by Plant)")

flowchart_dot = f"""
digraph G {{
    node [shape=box, style=filled, color=lightblue, fontname=Helvetica];
    "Total Materials\n({total_materials})" -> "PD/V1 Classification\n({pd_v1_count})";
    "Total Materials\n({total_materials})" -> "ND Classification\n({nd_count})";
}}
"""

st.graphviz_chart(flowchart_dot)

# Simple Data Preview
st.subheader("Filtered Material Data Preview")
st.dataframe(filtered_removed.head(50))
