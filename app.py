from flask import Flask, request, send_file
import pyembroidery
from PIL import Image, ImageDraw
import io
import os
import tempfile

app = Flask(__name__)

@app.route('/process-emb', methods=['POST'])
def process_emb():
    if 'file' not in request.files:
        return "No file uploaded", 400
    
    file = request.files['file']
    file_bytes = file.read()
    
    tmp_path = None
    try:
        # Guardar archivo temporal para lectura vectorial
        with tempfile.NamedTemporaryFile(delete=False, suffix='.emb') as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        pattern = pyembroidery.read(tmp_path)
        if pattern and len(pattern.stitches) > 0:
            bounds = pattern.bounds()
            min_x, min_y, max_x, max_y = bounds[0], bounds[1], bounds[2], bounds[3]
            
            margin = 50
            width = int(max_x - min_x) + (margin * 2)
            height = int(max_y - min_y) + (margin * 2)

            width = max(width, 600)
            height = max(height, 600)

            # Lienzo oscuro
            img = Image.new('RGBA', (width, height), (18, 18, 18, 255))
            draw = ImageDraw.Draw(img)

            offset_x = -min_x + margin
            offset_y = -min_y + margin

            # Recorrer los bloques de color del bordado
            for stitches, thread in pattern.get_as_colorblocks():
                rgb = thread.get_rgb() if thread else (255, 255, 255)
                color_tuple = (rgb[0], rgb[1], rgb[2], 255)
                
                last_pt = None
                for stitch in stitches:
                    x = stitch[0] + offset_x
                    y = stitch[1] + offset_y
                    flags = stitch[2]

                    if flags == pyembroidery.STITCH:
                        if last_pt:
                            draw.line([last_pt, (x, y)], fill=color_tuple, width=3)
                        last_pt = (x, y)
                    else:
                        last_pt = None

            output_io = io.BytesIO()
            img.save(output_io, 'PNG')
            output_io.seek(0)
            return send_file(output_io, mimetype='image/png')

    except Exception as e:
        print(f"Error trazando puntadas: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Si el patrón no se pudo decodificar, genera el recuadro informativo
    img_fallback = Image.new('RGB', (800, 800), color=(18, 18, 18))
    draw_f = ImageDraw.Draw(img_fallback)
    draw_f.rectangle([20, 20, 780, 780], outline=(233, 30, 99), width=4)
    draw_f.text((400, 400), "Needle.Knot Studio - Vista Vectorial", fill=(255, 255, 255), anchor="mm")
    
    out = io.BytesIO()
    img_fallback.save(out, format='PNG')
    out.seek(0)
    return send_file(out, mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
