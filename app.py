from flask import Flask, request, send_file
import olefile
import io
import re
from PIL import Image

app = Flask(__name__)

@app.route('/process-emb', methods=['POST'])
def process_emb():
    if 'file' not in request.files:
        return "No file uploaded", 400
    
    file = request.files['file']
    file_bytes = io.BytesIO(file.read())
    
    # Validar si es un contenedor OLE real de Wilcom
    if not olefile.isOleFile(file_bytes):
        return "El archivo no es un .EMB válido", 400

    try:
        ole = olefile.OleFileIO(file_bytes)
        preview_data = None

        # Escanear TODOS los flujos internos del EMB
        for stream_name in ole.listdir():
            try:
                data = ole.openstream(stream_name).read()
                # Buscar cabeceras de imagen: JPEG (\xFF\xD8\xFF), PNG (\x89PNG), BMP (\x42\x4D)
                match = re.search(b'(\xFF\xD8\xFF|\x89PNG|\x42\x4D)', data)
                if match:
                    raw_bytes = data[match.start():]
                    try:
                        # Comprobar si PIL logra decodificar la imagen
                        test_img = Image.open(io.BytesIO(raw_bytes))
                        test_img.verify()
                        preview_data = raw_bytes
                        break
                    except Exception:
                        continue
            except Exception:
                continue
        
        if preview_data:
            img = Image.open(io.BytesIO(preview_data))
            output_io = io.BytesIO()
            img.save(output_io, 'PNG', quality=100)
            output_io.seek(0)
            return send_file(output_io, mimetype='image/png')
            
    except Exception as e:
        return f"Error procesando EMB: {str(e)}", 500

    return "No se detectó miniatura interna en el archivo .EMB", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
