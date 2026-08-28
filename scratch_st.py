import streamlit as st
try:
    st.download_button("Download", data=bytearray(b'hello'), file_name="test.txt")
    print("Success")
except Exception as e:
    print(f"Failed with {type(e)}: {e}")
