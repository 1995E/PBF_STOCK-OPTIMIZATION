import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import io
import re

st.set_page_config(
    page_title="PBF STOCK ANALYSE TOOL",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CHOOSE THE IMPACTED PLANT IN SIDEBAR
with st.sidebar:
    st.markdown("### 🚢 Plant Selection")
    plant = st.selectbox(
        "Select the impacted Plant:",
        ['GIRASSOL', 'DALIA', 'PAZFLOR', 'CLOV', 'GENERAL DIVISION'],
    )

# 1. FILE UPLOADERS IN SIDEBAR
with st.sidebar:
    st.header("📂 Data Source Configuration")
    uploaded_materials = st.file_uploader("Material Overview per Plant (Excel)", type=["xlsx"])
    uploaded_prices = st.file_uploader("Material Overview per Price (Excel)", type=["xlsx"])
    st.markdown("---")

if uploaded_materials is not None and uploaded_prices is not None:
    # Read DataFrames
    removed_materials_df = pd.read_excel(uploaded_materials)
    unit_price_df = pd.read_excel(uploaded_prices)

    # 2. PROCESSING INFORMATION
    filtered_unit_prices = unit_price_df[unit_price_df['Valuation Type'] == 'BLOC-17']
    material_prices = filtered_unit_prices.groupby('Material n°')['Item Price'].mean()
    removed_materials_df['Unit price'] = removed_materials_df['Material n°'].map(material_prices)

    requested_columns = [
        'Material n°', 'Material description', 'Material discipline',
        'Plant code', 'Plant', 'Storage bin', 'FASD', 'Blocking status',
        'Gest', 'MRP Type', 'Stock qty', 'Blocked Stock Qty',
        'Safety', 'Min', 'Max', 'Unit price'
    ]
    existing_columns = [col for col in requested_columns if col in removed_materials_df.columns]
    df = removed_materials_df[existing_columns].copy()

    # Perform calculations
    Total_removed_materials = df['Material n°'].nunique()
    pd_v1_df = df[df['MRP Type'].isin(['PD', 'V1'])].copy()
    pd_v1_unique_materials = pd_v1_df.drop_duplicates(subset=['Material n°'])
    stock_greater_zero = pd_v1_df[pd_v1_df['Stock qty'] > 0]

    Interested_plant = stock_greater_zero[stock_greater_zero['Plant'] == plant].copy()
    Interested_plant_unique = Interested_plant.drop_duplicates(subset=['Material n°']).copy()

    Others_plant = pd_v1_df[pd_v1_df['Plant'] != plant].copy()
    Others_plant_unique = Others_plant.drop_duplicates(subset=['Material n°']).copy()

    Total_stock_value = (stock_greater_zero['Stock qty'] *  stock_greater_zero['Unit price']).sum()
    Interested_plant_stock_value = (Interested_plant['Stock qty'] * Interested_plant['Unit price']).sum()
    Others_plant_stock_value = Total_stock_value - Interested_plant_stock_value
    Interested_plant['Stock Value'] = Interested_plant['Stock qty'] * Interested_plant['Unit price'].fillna(0)

    # Modern Title
    st.markdown("<h1 style='color: #1E3A8A; font-family: serif;'>PBF Stock Analyse Tool</h1>", unsafe_allow_html=True)

    # Tab layouts
    tab1, tab2, tab3 = st.tabs(["📊 DISPLAY CHARTS", "🔍 CHARTS FOR MATERIAL GROUP", "📋 DETAILED DATASET"])

    with tab1:
        st.markdown("### 📈 High-Level Assessments & Value Share")
        col_sunburst, col_pie = st.columns([1.1, 0.9])
        
        with col_sunburst:
            st.markdown("##### MATERIAL ASSESSMENT STRUCTURE (SUNBURST CHART)")
            
            # Hierarchical values calculated from core df
            total_assessed = df['Material n°'].nunique()
            is_stock = df['MRP Type'].isin(['PD', 'V1'])
            stock_mats = df[is_stock]
            non_stock_mats = df[~is_stock]
            
            cnt_stock_total = stock_mats['Material n°'].nunique()
            cnt_non_stock_total = total_assessed - cnt_stock_total
            
            # Count discipline groups (SE, SU, MM) inside Stock vs Non-Stock
            stock_disc = stock_mats[stock_mats['Material discipline'].isin(['SE', 'SU', 'MM'])].groupby('Material discipline')['Material n°'].nunique().to_dict()
            non_stock_disc = non_stock_mats[non_stock_mats['Material discipline'].isin(['SE', 'SU', 'MM'])].groupby('Material discipline')['Material n°'].nunique().to_dict()
            
            stock_se = stock_disc.get('SE', 0)
            stock_su = stock_disc.get('SU', 0)
            stock_mm = stock_disc.get('MM', 0)
            stock_other = cnt_stock_total - (stock_se + stock_su + stock_mm)
            
            ns_se = non_stock_disc.get('SE', 0)
            ns_su = non_stock_disc.get('SU', 0)
            ns_mm = non_stock_disc.get('MM', 0)
            ns_other = cnt_non_stock_total - (ns_se + ns_su + ns_mm)
            
            # Setup Sunburst nodes
            ids = [
                "Total Assessed",
                "Stock Materials", "Non-Stock Materials",
                "Stock_SE", "Stock_SU", "Stock_MM", "Stock_Other",
                "NS_SE", "NS_SU", "NS_MM", "NS_Other"
            ]
            labels = [
                f"Total Assessed<br>({total_assessed:,})",
                f"Stock Materials<br>({cnt_stock_total:,})", f"Non-Stock Materials<br>({cnt_non_stock_total:,})",
                f"SE ({stock_se})", f"SU ({stock_su})", f"MM ({stock_mm})", f"Other ({max(0, stock_other)})",
                f"SE ({ns_se})", f"SU ({ns_su})", f"MM ({ns_mm})", f"Other ({max(0, ns_other)})"
            ]
            parents = [
                "",
                "Total Assessed", "Total Assessed",
                "Stock Materials", "Stock Materials", "Stock Materials", "Stock Materials",
                "Non-Stock Materials", "Non-Stock Materials", "Non-Stock Materials", "Non-Stock Materials"
            ]
            values = [
                total_assessed,
                cnt_stock_total, cnt_non_stock_total,
                stock_se, stock_su, stock_mm, max(0, stock_other),
                ns_se, ns_su, ns_mm, max(0, ns_other)
            ]
            
            fig_sunburst = go.Figure(go.Sunburst(
                ids=ids,
                labels=labels,
                parents=parents,
                values=values,
                branchvalues="total",
                marker=dict(colors=px.colors.qualitative.Pastel)
            ))
            fig_sunburst.update_layout(height=450, margin=dict(t=10, l=10, r=10, b=10))
            st.plotly_chart(fig_sunburst, use_container_width=True)
            
        with col_pie:
            st.markdown("##### STOCK VALUE SHARE PER PLANT (PIE CHART)")
            
            if not stock_greater_zero.empty:
                stock_greater_zero['Calculated Value'] = stock_greater_zero['Stock qty'] * stock_greater_zero['Unit price'].fillna(0)
                plant_shares = stock_greater_zero.groupby('Plant')['Calculated Value'].sum().reset_index()
                
                fig_pie = px.pie(
                    plant_shares,
                    values='Calculated Value',
                    names='Plant',
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Safe
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(
                    height=450,
                    margin=dict(t=10, l=10, r=10, b=10),
                    legend=dict(orientation="h", y=-0.1, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No active stock materials to calculate plant value distribution.")

    with tab2:
        st.markdown("### 🔍 Group Assessment Filters")
        st.info("Choose a material category or classification from the sidebar or select a specific material group to display metrics here.")

    with tab3:
        st.markdown("### 📋 Materials Database Overview")
        st.dataframe(df, use_container_width=True)
else:
    st.info("💡 Please upload both 'Material Overview per Plant' and 'Material Overview per Price' Excel files in the sidebar to get started!")
