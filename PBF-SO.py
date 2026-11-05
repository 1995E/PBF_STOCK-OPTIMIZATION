st.header("📂 Data Source Configuration")
uploaded_materials = st.file_uploader("Material Overview per Plant (Excel)", type=["xlsx"])
uploaded_prices = st.file_uploader("Material Overview per Price (Excel)", type=["xlsx"])
    Bom_template = st.file_uploader("Bom template (Excel)", type=["xlsx"])
st.markdown("---")

if uploaded_materials is not None and uploaded_prices is not None:
# Read DataFrames
removed_materials_df = pd.read_excel(uploaded_materials)
unit_price_df = pd.read_excel(uploaded_prices)
    

# 2. PROCESSING INFORMATION
filtered_unit_prices = unit_price_df[unit_price_df['Valuation Type'] == 'BLOC-17']
material_prices = filtered_unit_prices.groupby('Material n°')['Item Price'].mean()
@@ -42,14 +43,13 @@

# DYNAMIC PLANT SELECTOR IN SIDEBAR
with st.sidebar:
        available_plants = sorted(df['Plant'].dropna().unique())  
        available_plants = sorted(df['Plant'].dropna().unique())
plant = st.selectbox(
"Select Plant of Interest:",
available_plants,
index=0 if 'PAZFLOR' not in available_plants else available_plants.index('PAZFLOR'),
)
    
    

# Perform calculations based on selection
Total_removed_materials = df['Material n°'].nunique()
pd_v1_df = df[df['MRP Type'].isin(['PD', 'V1'])].copy()
@@ -74,7 +74,60 @@
with kpi4:
st.markdown(f'<div class="metric-card"><h6>Potential {plant} Dead Stock Value (USD)</h6><h3>${Interested_plant_stock_value:,.2f}</h3></div>', unsafe_allow_html=True)

# 1. FILE UPLOADERS IN SIDEBAR
with st.sidebar:
    Bom_template = st.file_uploader("Bom template (Excel)", type=["xlsx"])
    st.markdown("---")
    # 4. BOM ANALYSIS MAPPING
    if Bom_template is not None:
        try:
            # Load BOM & BOM Assignment sheets
            bom_sheet_df = pd.read_excel(Bom_template, sheet_name="BOM")
            bom_assignment_df = pd.read_excel(Bom_template, sheet_name="BOM Assignment")
            
            # Clean column names just in case
            bom_sheet_df.columns = bom_sheet_df.columns.str.strip()
            bom_assignment_df.columns = bom_assignment_df.columns.str.strip()

            # Rename assembly reference key in BOM sheet and join with plant unique list
            # Typically BOM sheet associates Material reference -> Assembly
            # Let's map Interested_plant_unique['Material n°'] to Assembly
            mapping_df = Interested_plant_unique[['Material n°']].copy()
            mapping_df['Material n°'] = mapping_df['Material n°'].astype(str).str.strip()
            
            bom_sheet_df['Material reference'] = bom_sheet_df['Material reference'].astype(str).str.strip()
            bom_sheet_df['Assembly'] = bom_sheet_df['Assembly'].astype(str).str.strip()
            
            # Merge to get the associated Assembly reference
            merged_bom = pd.merge(
                mapping_df, 
                bom_sheet_df[['Material reference', 'Assembly']], 
                left_on='Material n°', 
                right_on='Material reference', 
                how='left'
            )
            
            # Rename 'Assembly' to 'Sub-assembly'
            merged_bom.rename(columns={'Assembly': 'Sub-assembly'}, inplace=True)
            
            # Use Assembly reference value to go to BOM Assignment sheet and get associated FL
            bom_assignment_df['Assembly'] = bom_assignment_df['Assembly'].astype(str).str.strip()
            bom_assignment_df['FL'] = bom_assignment_df['FL'].astype(str).str.strip()
            
            final_bom_df = pd.merge(
                merged_bom, 
                bom_assignment_df[['Assembly', 'FL']], 
                left_on='Sub-assembly', 
                right_on='Assembly', 
                how='left'
            )
            
            # Rename FL to Functional Locations
            final_bom_df.rename(columns={'FL': 'Functional Locations'}, inplace=True)
            
            # Structure final dataframe columns
            final_display_df = final_bom_df[['Material n°', 'Sub-assembly', 'Functional Locations']].drop_duplicates()
            
            st.markdown("### 📋 BOM Assignment Overview")
            st.dataframe(final_display_df, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error processing BOM template sheets: {e}")
    else:
        st.warning("Please upload the BOM template to view Assembly and Functional Locations mappings.")
