import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import io

st.set_page_config(
    page_title="Material Analysis Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📦 Material Overview & Stock Analysis")
st.markdown("Retrieve structured insights, classify inventory status, and assess material for scrapping or to be transferred.")

# 1. FILE UPLOADERS IN SIDEBAR
with st.sidebar:
    st.header("📂 Data Source Configuration")
    uploaded_materials = st.file_uploader("Material Overview per Plant (Excel)", type=["xlsx"])
    uploaded_prices = st.file_uploader("Material Overview per Price (Excel)", type=["xlsx"])
    st.markdown("---")

with st.sidebar:
    Bom_template = st.file_uploader("Impacted Bom (Excel)", type=["xlsx"])
    st.markdown("---")

if uploaded_materials is not None and uploaded_prices is not None:
    # Read DataFrames
    removed_materials_df = pd.read_excel(uploaded_materials)
    unit_price_df = pd.read_excel(uploaded_prices)

    # 2. PROCESSING INFORMATION
    filtered_unit_prices = unit_price_df[unit_price_df['Valuation Type'] == 'BLOC-17']
    material_prices = filtered_unit_prices.groupby('Material n°')['Item Price'].mean()
    #removed_materials_df['Unit price'] = removed_materials_df['Material n°'].map(material_prices)

    requested_columns = [
        'Material n°', 'Material description', 'Material discipline',
        'Plant code', 'Plant', 'storage bin', 'FASD', 'Blocking status',
        'MRP Type', 'Stock qty', 'Blocked Stock Qty', 'Safety', 'Min',
        'Max', 'Unit price'
    ]
    existing_columns = [col for col in requested_columns if col in removed_materials_df.columns]
    df = removed_materials_df[existing_columns].copy()

    # DYNAMIC PLANT SELECTOR IN SIDEBAR
    with st.sidebar:
        available_plants = sorted(df['Plant'].dropna().unique())
        plant = st.selectbox(
            "Select Plant of Interest:",
            available_plants,
            index=0 if 'PAZFLOR' not in available_plants else available_plants.index('PAZFLOR'),
        )

    # Perform calculations based on selection
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

    # UPDATE INTERESTED PLANT DATAFRAME WITH ACTION COLUMN FROM IMPACTED BOM BEFORE DISPLAYING KPIs
    scrap_value = 0.0
    transfer_value = 0.0
    bom_loaded = False
    materials_to_transfer = pd.DataFrame()

    if Bom_template is not None:
        try:
            material_list_df = pd.read_excel(Bom_template, sheet_name="Material_List")
            material_list_df.columns = material_list_df.columns.str.strip()

            # Clean mapping IDs to prevent string/numeric mismatch issues
            material_list_df['Material n°'] = material_list_df['Material n°'].astype(str).str.strip()
            Interested_plant['Material n°'] = Interested_plant['Material n°'].astype(str).str.strip()
            Others_plant['Material n°'] = Others_plant['Material n°'].astype(str).str.strip()

            # Group by material number if there are duplicates to get unique mapping values
            action_mapping = material_list_df.set_index('Material n°')['Results'].to_dict()
            Interested_plant['Action'] = Interested_plant['Material n°'].map(action_mapping)

            # Create default status column
            Interested_plant['Optimization Status'] = 'Standard'

            # Rule: If Action is "FASD analyse" and FASD status is "Dead", update Action to "Scrap analyse" and Optimization Status to "Optimized"
            mask = (Interested_plant['Action'] == 'FASD analyse') & (Interested_plant['FASD'] == 'Dead')
            Interested_plant.loc[mask, 'Action'] = 'Scrap analyse'
            Interested_plant.loc[mask, 'Optimization Status'] = 'Optimized'

            # Identify material n° belonging to Interested_plant's "Scrap analyse" list
            scrap_analyse_materials = Interested_plant[Interested_plant['Action'] == 'Scrap analyse']['Material n°'].unique()

            # Filter Others_plant where FASD is not "Dead" and material exists in the Scrap analyse list
            active_others_df = Others_plant[(Others_plant['Material n°'].isin(scrap_analyse_materials)) & (Others_plant['FASD'] != 'Dead')].copy()

            # Priority mapper based on FASD status
            priority_map = {'FAST': 1, 'Active': 2, 'Slow': 3}
            active_others_df['Priority'] = active_others_df['FASD'].map(priority_map).fillna(4)

            # Sort so that highest priority (FAST) comes first
            active_others_df = active_others_df.sort_values(by=['Material n°', 'Priority'])
            best_receiving_plants = active_others_df.drop_duplicates(subset=['Material n°']).set_index('Material n°')

            transfer_material_ids = best_receiving_plants.index.unique()

            # Split Interested_plant: extract materials to be transferred
            raw_transfer_df = Interested_plant[Interested_plant['Material n°'].isin(transfer_material_ids)].copy()
            Interested_plant = Interested_plant[~Interested_plant['Material n°'].isin(transfer_material_ids)].copy()

            # Assign Receiving plant and quantity
            if not raw_transfer_df.empty:
                raw_transfer_df['Receiving plant'] = raw_transfer_df['Material n°'].map(best_receiving_plants['Plant'])
                # Quantity is mapped to the inventory stock quantity of the item
                raw_transfer_df['quantity'] = raw_transfer_df['Stock qty']

                # Keep only specific requested columns (including storage bin)
                target_cols = [
                    'Material n°', 'Material description', 'Material discipline',
                    'Plant code', 'Plant', 'storage bin', 'FASD', 'Stock qty', 'Unit price',
                    'Receiving plant', 'quantity'
                ]
                existing_target_cols = [c for c in target_cols if c in raw_transfer_df.columns]
                materials_to_transfer = raw_transfer_df[existing_target_cols].copy()
                transfer_value = (materials_to_transfer['Stock qty'] * materials_to_transfer['Unit price']).sum()
            else:
                materials_to_transfer = pd.DataFrame()
                transfer_value = 0.0

            # Calculate Scrap Value for the remaining items in Interested_plant
            scrap_df = Interested_plant[Interested_plant['Action'] == 'Scrap analyse']
            scrap_value = (scrap_df['Stock qty'] * scrap_df['Unit price']).sum()

            bom_loaded = True
        except Exception as e:
            st.error(f"Error reading Material_List from Impacted Bom: {e}")

    # 3. HIGHLY VISUAL KPI METRICS SECTION
    st.markdown("### MAIN HIGHLIGHTS")
    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

    with kpi1:
        st.markdown(f'<div class="metric-card"><h6>Total Removed Materials</h6><h3>{Total_removed_materials:,}</h3></div>', unsafe_allow_html=True)
    with kpi2:
        st.markdown(f'<div class="metric-card"><h6>Total Stock Materials</h6><h3>{len(pd_v1_unique_materials):,}</h3></div>', unsafe_allow_html=True)
    with kpi3:
        st.markdown(f'<div class="metric-card"><h6>Total Stock Value (USD)</h6><h3>${Total_stock_value:,.2f}</h3></div>', unsafe_allow_html=True)
    with kpi4:
        st.markdown(f'<div class="metric-card"><h6>Potential {plant} Dead Stock Value (USD)</h6><h3>${Interested_plant_stock_value:,.2f}</h3></div>', unsafe_allow_html=True)
    with kpi5:
        if bom_loaded:
            st.markdown(f'<div class="metric-card" style="border-left: 5px solid red;"><h6>Scrap Analyse Value for {plant} (USD)</h6><h3>${scrap_value:,.2f}</h3></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="metric-card" style="color: gray;"><h6>Scrap Analyse Value</h6><h3>N/A</h3><small>Upload Impacted Bom</small></div>', unsafe_allow_html=True)
    with kpi6:
        if bom_loaded:
            st.markdown(f'<div class="metric-card" style="border-left: 5px solid green;"><h6>Materials to Transfer Value (USD)</h6><h3>${transfer_value:,.2f}</h3></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="metric-card" style="color: gray;"><h6>Transfer Value</h6><h3>N/A</h3><small>Upload Impacted Bom</small></div>', unsafe_allow_html=True)

    # Display Dataframe
    if bom_loaded:
        st.markdown(f"### 📋 Interested Plant Materials for {plant} (with Actions & Optimization Rules)")
        st.dataframe(Interested_plant, use_container_width=True)
        
        # Export Option for Interested Plant
        buffer_interested = io.BytesIO()
        with pd.ExcelWriter(buffer_interested, engine='openpyxl') as writer:
            Interested_plant.to_excel(writer, index=False, sheet_name='Interested Plant')
        st.download_button(
            label="📥 Download Interested Plant Excel",
            data=buffer_interested.getvalue(),
            file_name=f"Interested_Plant_{plant}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.markdown("### 🔄 Materials to be Transferred (Active in other plants, FASD != 'Dead')")
        if not materials_to_transfer.empty:
            st.dataframe(materials_to_transfer, use_container_width=True)
            
            # Export Option for Materials to Transfer
            buffer_transfer = io.BytesIO()
            with pd.ExcelWriter(buffer_transfer, engine='openpyxl') as writer:
                materials_to_transfer.to_excel(writer, index=False, sheet_name='Materials to Transfer')
            st.download_button(
                label="📥 Download Materials to Transfer Excel",
                data=buffer_transfer.getvalue(),
                file_name=f"Materials_to_Transfer_{plant}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No matching materials to transfer.")
    else:
        st.markdown(f"### 📋 Interested Plant Materials for {plant}")
        st.dataframe(removed_materials_df, use_container_width=True)
