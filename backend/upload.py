import os

def handle_upload(uploaded_file, upload_dir="data"):
    """保存上传的文件并返回路径"""
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, uploaded_file.name)
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return filepath
