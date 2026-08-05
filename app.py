from flask import Flask, request, send_file
import olefile
from PIL import Image
import io
import struct
import zipfile

app = Flask(__name__)

def dib_to_bmp(dib):
    """Reconstruye la cabecera BMP exacta para la miniatura DIB de Wilcom."""
    if len(dib) < 40:
        return None
    
    biSize = struct.unpack('<I', dib[:4])[0]
    if biSize != 40:  # BITMAPINFOHEADER estándar de Wilcom
        return None
    
    try:
        biBitCount = struct.unpack('<H', dib[14:16])[0]
        biCompression = struct.unpack('<I', dib[16:20])[0]
        biClrUsed = struct.unpack('<I', dib[32:36])[0]

        if biClrUsed > 0:
            num_colors = biClrUsed
        elif biBitCount <= 8:
            num_colors = 1 << biBitCount
        else:
            num_colors = 0

        palette_size = num_colors * 4
        if biCompression in (3, 6):
            palette_size += 12

        off_bits = 14 + biSize + palette_size
        file_size = 14 + len(dib)

        bmp_header = struct.pack('<2sIHHI', b'BM', file_size, 0, 0, off_bits)
        return bmp_header + dib
    except Exception:
        return None

def find_image_in_bytes(data):
    """Escanea el flujo binario en busca de miniaturas DIB, PNG o JPG de Wilcom."""
    # 1. Búsqueda de PNG
    png_idx = data.find(b'\x89PNG\r\n\x1a\n')
    if png_idx != -1:
        try:
            return Image.open(io.BytesIO(data[png_idx:]))
        except Exception:
            pass

    # 2. Búsqueda de JPG
    jpg_idx = data.find(b'\xFF\xD8\xFF')
    if jpg_idx != -1:
        try:
            return Image.open(io.BytesIO(data[jpg_idx:]))
        except Exception:
            pass

    # 3. Búsqueda de mapa de bits DIB (biSize = 40)
    pos = 0
    while True:
        pos = data.find(b'\x28\x00\x00\x00', pos)
        if pos == -1:
            break
        bmp_data = dib_to_bmp(data[pos:])
        if bmp_data:
            try:
                img = Image.open(io.BytesIO(bmp_data))
                if img.width > 20 and img.height > 20:
                    return img
            except Exception:
                pass
        pos += 1

    return None

@app.route('/process-emb', methods=['POST'])
def process_emb():
    if 'file' not in request.files:
        return "No file uploaded", 400
    
    file = request.files['file']
    file_bytes = file.read()
    file_io = io.BytesIO(file_bytes)

    # 1. Wilcom reciente (Contenedor ZIP)
    if zipfile.is_zipfile(file_io):
        try:
            with zipfile.ZipFile(file_io) as z:
                for name in z.namelist():
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                        img = Image.open(io.BytesIO(z.read(name)))
                        out = io.BytesIO()
                        img.save(out, 'PNG')
                        out.seek(0)
                        return send_file(out, mimetype='image/png')
        except Exception:
            pass
        file_io.seek(0)

    # 2. Wilcom estándar (Contenedor OLE / SummaryInformation)
    if olefile.isOleFile(file_io):
        try:
            ole = olefile.OleFileIO(file_io)
            
            # Revisar metadatos oficiales del diseño
            meta = ole.get_metadata()
            if meta.thumbnail:
                img = find_image_in_bytes(meta.thumbnail)
                if img:
                    out = io.BytesIO()
                    img.save(out, 'PNG')
                    out.seek(0)
                    return send_file(out, mimetype='image/png')

            # Escanear flujos internos
            for stream_path in ole.listdir():
                try:
                    stream_data = ole.openstream(stream_path).read()
                    img = find_image_in_bytes(stream_data)
                    if img:
                        out = io.BytesIO()
                        img.save(out, 'PNG')
                        out.seek(0)
                        return send_file(out, mimetype='image/png')
                except Exception:
                    continue
        except Exception:
            pass

    # 3. Escaneo directo de respaldo
    img = find_image_in_bytes(file_bytes)
    if img:
        out = io.BytesIO()
        img.save(out, 'PNG')
        out.seek(0)
        return send_file(out, mimetype='image/png')

    return "No preview found in EMB", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
