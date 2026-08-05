from flask import Flask, request, send_file
import olefile
from PIL import Image
import io
import re
import struct

app = Flask(__name__)

def dib_to_bmp(dib_data):
    """Agrega la cabecera 'BM' a los bloques DIB de Wilcom para que Pillow los lea."""
    try:
        if len(dib_data) < 40:
            return None
        header_size = struct.unpack('<I', dib_data[:4])[0]
        if header_size not in (40, 56, 108, 124):
            return None
        
        file_size = 14 + len(dib_data)
        bmp_header = struct.pack('<2sIHHI', b'BM', file_size, 0, 0, 14 + header_size)
        return bmp_header + dib_data
    except Exception:
        return None

@app.route('/process-emb', methods=['POST'])
def process_emb():
    if 'file' not in request.files:
        return "No file uploaded", 400
    
    file = request.files['file']
    file_bytes = file.read()
    
    file_io = io.BytesIO(file_bytes)
    if not olefile.isOleFile(file_io):
        return "El archivo no es un EMB válido", 400

    try:
        ole = olefile.OleFileIO(file_io)
        
        for stream_name in ole.listdir():
            try:
                data = ole.openstream(stream_name).read()
                
                # 1. Buscar imágenes PNG o JPG estándar
                match = re.search(b'(\xFF\xD8\xFF|\x89PNG)', data)
                if match:
                    raw_bytes = data[match.start():]
                    img = Image.open(io.BytesIO(raw_bytes))
                    output_io = io.BytesIO()
                    img.save(output_io, 'PNG')
                    output_io.seek(0)
                    return send_file(output_io, mimetype='image/png')

                # 2. Buscar cabecera DIB de Windows (usada por Wilcom)
                dib_index = data.find(b'\x28\x00\x00\x00')
                if dib_index != -1:
                    dib_data = data[dib_index:]
                    bmp_bytes = dib_to_bmp(dib_data)
                    if bmp_bytes:
                        try:
                            img = Image.open(io.BytesIO(bmp_bytes))
                            output_io = io.BytesIO()
                            img.save(output_io, 'PNG')
                            output_io.seek(0)
                            return send_file(output_io, mimetype='image/png')
                        except Exception:
                            pass
            except Exception:
                continue

    except Exception as e:
        return f"Error leyendo OLE: {str(e)}", 500

    return "No se pudo extraer la vista previa del archivo EMB", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
