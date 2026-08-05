from flask import Flask, request, send_file
import olefile
import pyembroidery
from PIL import Image, ImageDraw
import io
import re
import tempfile
import os

app = Flask(__name__)

@app.route('/process-emb', methods=['POST'])
def process_emb():
    if 'file' not in request.files:
        return "No file uploaded", 400
    
    file = request.files['file']
    file_bytes = file.read()
    
    # Intento 1: Extraer miniatura incrustada si existe
    try:
        file_io = io.BytesIO(file_bytes)
        if olefile.isOleFile(file_io):
            ole = olefile.OleFileIO(file_io)
            for stream_name in ole.listdir():
                try:
                    data = ole.openstream(stream_name).read()
                    match = re.search(b'(\xFF\xD8\xFF|\x89PNG|\x42\x4D)', data)
                    if match:
                        raw_bytes = data[match.start():]
                        img = Image.open(io.BytesIO(raw_bytes))
                        output_io = io.BytesIO()
                        img.save(output_io, 'PNG', quality=100)
                        output_io.seek(0)
                        return send_file(output_io, mimetype='image/png')
                except Exception:
                    continue
    except Exception:
        pass

    # Intento 2: Generar trazado vectorial a partir de las puntadas
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.emb') as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        pattern = pyembroidery.read(tmp_path)
        if pattern and len(pattern.stitches) > 0:
            bounds = pattern.bounds()
            min_x, min_y, max_x, max_y = bounds[0], bounds[1], bounds[2], bounds[3]
            
            margin = 30
            width = int(max_x - min_x) + (margin * 2)
            height = int(max_y - min_y) + (margin * 2)

            width = max(width, 400)
            height = max(height, 400)

            # Lienzo oscuro industrial
            img = Image.new('RGBA', (width, height), (18, 18, 18, 255))
            draw = ImageDraw.Draw(img)

            offset_x = -min_x + margin
            offset_y = -min_y + margin

            last_pt = None
            for stitch in pattern.stitches:
                x = stitch[0] + offset_x
                y = stitch[1] + offset_y
                flags = stitch[2]

                if flags == pyembroidery.STITCH:
                    if last_pt:
                        # Trazado en tono rosado satinado con relieve
                        draw.line([last_pt, (x, y)], fill=(233, 30, 99, 255), width=2)
                    last_pt = (x, y)
                else:
                    last_pt = None

            output_io = io.BytesIO()
            img.save(output_io, 'PNG')
            output_io.seek(0)
            return send_file(output_io, mimetype='image/png')

    except Exception as e:
        return f"Error leyendo puntadas: {str(e)}", 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    return "No se pudo procesar la estructura del archivo EMB", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
