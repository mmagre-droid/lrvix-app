import streamlit as st
from supabase import create_client

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]

st.write("URL lida:", url)
st.write("Chave lida (primeiros caracteres):", key[:15] if key else "VAZIO")

try:
    supabase = create_client(url, key)
    res = supabase.table("TECNICOS").select("count", count="exact").execute()
    st.success("Conexão com o Supabase realizada com sucesso!")
except Exception as e:
    st.error(f"Erro exato retornado pelo Supabase: {e}")
