import pdfplumber
import json

pdf_path = "UBICACION TIENDAS SAHAGUN PREVENTA .pdf"
all_text = ""

try:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        # Print a sample of the first page to understand structure
        first_page = pdf.pages[0]
        text = first_page.extract_text()
        print("--- FIRST PAGE TEXT SAMPLE ---")
        print(text[:1000])
        
        # Check for tables
        tables = first_page.extract_tables()
        if tables:
            print("--- FIRST PAGE TABLE SAMPLE ---")
            print(tables[0][:5])
            
except Exception as e:
    print(f"Error reading PDF: {e}")
