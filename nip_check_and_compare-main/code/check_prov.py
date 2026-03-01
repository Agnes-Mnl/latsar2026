import pandas as pd
excel_path = r"C:\Users\agnes\Documents\0. LATSAR\nip_check_and_compare-main\nip_check_and_compare-main\Provinsi.xlsx"
xls = pd.ExcelFile(excel_path)
for sheet_name in xls.sheet_names:
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    print(f"Sheet: {sheet_name}, Columns: {df.columns.tolist()}")
