from utils.data_loader import load_data
data = load_data()
df_cli = data['clientes']
print(df_cli.columns)
if 'Vendedor' in df_cli.columns:
    print(df_cli[['Nombre', 'Vendedor']].head(2))
else:
    print("No Vendedor column in df_cli")
