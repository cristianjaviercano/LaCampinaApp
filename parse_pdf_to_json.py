import pdfplumber
import pandas as pd
import json
import re

pdf_path = "UBICACION TIENDAS SAHAGUN PREVENTA .pdf"
all_data = []

def clean_coord(c):
    if not c: return None, None
    c = str(c).replace(',', ' ').replace('...', '.').strip()
    # Find all float-like numbers
    nums = re.findall(r'-?\d+\.\d+', c)
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    return None, None

try:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Skip header rows
                    if not row or str(row[0]).strip().upper() == 'NOMBRE':
                        continue
                    
                    if len(row) >= 3:
                        nombre = str(row[0]).strip() if row[0] else ""
                        barrio = str(row[1]).strip() if row[1] else ""
                        coord_str = row[2]
                        lat, lon = clean_coord(coord_str)
                        
                        if nombre:
                            all_data.append({
                                'Cliente': nombre,
                                'Barrio': barrio,
                                'Latitud': lat,
                                'Longitud': lon
                            })

    df = pd.DataFrame(all_data)
    # Remove duplicates
    df = df.drop_duplicates(subset=['Cliente'], keep='first')
    
    # Save to JSON
    out_file = "ubicaciones_pdf_extraidas.json"
    df.to_json(out_file, orient='records', force_ascii=False, indent=4)
    print(f"Éxito: Se extrajeron {len(df)} ubicaciones únicas y se guardaron en {out_file}")
    
    # Also save to excel for easy viewing
    out_excel = "ubicaciones_pdf_extraidas.xlsx"
    df.to_excel(out_excel, index=False)

except Exception as e:
    print(f"Error procesando PDF: {e}")
