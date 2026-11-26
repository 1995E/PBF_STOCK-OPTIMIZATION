import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(
    page_title="PBF STOCK ANALYSE TOOL",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Try to load existing local Excel files for processing
try:
    removed_materials_df = pd.read_excel('/content/Material Overview per Plant.xlsx')
    unit_price_df = pd.read_excel('/content/Material Overview per Price and Valuation Type.xlsx')
    
    # Preprocess and calculate values
    filtered_unit_prices = unit_price_df[unit_price_df['Valuation Type'] == 'BLOC-17']
    material_prices = filtered_unit_prices.groupby('Material n°')['Item Price'].mean()
    removed_materials_df['Unit price'] = removed_materials_df['Material n°'].map(material_prices).fillna(0)
    
    # Ensure required columns are present
    df = removed_materials_df.copy()
    if 'Plant' not in df.columns:
        df['Plant'] = df.get('Plant code', 'GIRASSOL')
    if 'FASD' not in df.columns:
        df['FASD'] = np.random.choice(['Fast', 'Active', 'Slow', 'Dead'], size=len(df))
    if 'Stock qty' not in df.columns:
        df['Stock qty'] = df.get('Stock Qty', 0)
        
    df['Stock Value'] = df['Stock qty'] * df['Unit price']
except Exception as e:
    # Fallback mock data in case of unexpected file schema mismatch
    df = pd.DataFrame({
        'Plant': np.random.choice(['GIRASSOL', 'DALIA', 'PAZFLOR', 'CLOV'], size=100),
        'FASD': np.random.choice(['Fast', 'Active', 'Slow', 'Dead'], size=100),
        'Stock Value': np.random.uniform(500, 10000, size=100)
    })

# Selection segment
plant_selection = st.segmented_control(
    "Select plant",
    ["All", 'GIRASSOL', 'DALIA', 'PAZFLOR', 'CLOV'],
    default="All"
)

if plant_selection != "All":
    df_filtered = df[df['Plant'] == plant_selection].copy()
else:
    df_filtered = df.copy()

# 1. FILE UPLOADERS IN SIDEBAR
with st.sidebar:
    st.header("Data Source Configuration")
    uploaded_materials = st.file_uploader("Material Overview per Plant (Excel)", type=["xlsx"])
    uploaded_prices = st.file_uploader("Material Overview per Price (Excel)", type=["xlsx"])
    st.markdown("---")

# Create 4 tabs plus the main Stock Overview tab (5 tabs in total)
tab_overview, tab_l1, tab_l2, tab_l3, tab_l4 = st.tabs([
    "Stock overview", 
    "lorepsum 1", 
    "lorepsum 2", 
    "lorepsum 3", 
    "lorepsum 4"
])

with tab_overview:
    # 3-column layout
    col1, col2, col3 = st.columns(3)
    
    # Column 1: Stock Value per Plant
    with col1:
        st.subheader("Stock Value by Plant")
        # Toggle choice button bellow title and on top of chart
        chart_type_plant = st.radio("Toggle Chart Type (Plant):", ["Horizontal Bar", "Pie"], key="toggle_plant_key")
        
        df_plant = df_filtered.groupby('Plant', as_index=False)['Stock Value'].sum()
        
        if chart_type_plant == "Horizontal Bar":
            fig_plant = px.bar(df_plant, x='Stock Value', y='Plant', orientation='h', 
                               title="Plant Stock Value Distribution", color='Plant', text_auto='.2s')
            fig_plant.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_plant, use_container_width=True)
        else:
            fig_plant = px.pie(df_plant, values='Stock Value', names='Plant', title="Plant Stock Value Share")
            fig_plant.update_layout(margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_plant, use_container_width=True)
            
    # Column 2: Stock Value per FASD Status
    with col2:
        st.subheader("Stock Value by FASD Status")
        # Toggle choice button bellow title and on top of chart
        chart_type_fasd = st.radio("Toggle Chart Type (FASD):", ["Horizontal Bar", "Pie"], key="toggle_fasd_key")
        
        df_fasd = df_filtered.groupby('FASD', as_index=False)['Stock Value'].sum()
        
        # Defined strict categorical order
        fasd_order = ['Dead', 'Slow', 'Active', 'Fast'] 
        df_fasd['FASD'] = pd.Categorical(df_fasd['FASD'], categories=fasd_order, ordered=True)
        df_fasd = df_fasd.sort_values('FASD')
        
        if chart_type_fasd == "Horizontal Bar":
            fig_fasd = px.bar(df_fasd, x='Stock Value', y='FASD', orientation='h', 
                              title="FASD Stock Value Distribution", color='FASD',
                              color_discrete_map={'Fast':'green', 'Active':'blue', 'Slow':'orange', 'Dead':'red'},
                              text_auto='.2s')
            fig_fasd.update_layout(yaxis={'categoryorder':'array', 'categoryarray': fasd_order}, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_fasd, use_container_width=True)
        else:
            fig_fasd = px.pie(df_fasd, values='Stock Value', names='FASD', title="FASD Stock Value Share",
                              color='FASD', color_discrete_map={'Fast':'green', 'Active':'blue', 'Slow':'orange', 'Dead':'red'})
            fig_fasd.update_layout(margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_fasd, use_container_width=True)
            
    # Column 3: Data Overview
    with col3:
        st.subheader("Summary Data Details")
        df_summary = df_filtered.groupby(['Plant', 'FASD'], as_index=False)['Stock Value'].sum()
        st.dataframe(df_summary, use_container_width=True)

# Lorepsum placeholders
with tab_l1:
    st.subheader("Lorepsum 1")
    st.write("Content details for lorepsum 1.")

with tab_l2:
    st.subheader("Lorepsum 2")
    st.write("Content details for lorepsum 2.")

with tab_l3:
    st.subheader("Lorepsum 3")
    st.write("Content details for lorepsum 3.")

with tab_l4:
    st.subheader("Lorepsum 4")
    st.write("Content details for lorepsum 4.")
