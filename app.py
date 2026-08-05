from flask import Flask, request, send_file
import olefile
from PIL import Image
import io
import struct

app = Flask(__name__)

def dib_to_bmp(dib_data):
    """Calcula la paleta de colores y reconstruye la cabecera BMP limpia de Wilcom."""
    if len(dib_data) < 40:
        return None
    
    biSize = struct.unpack('<I', dib_data[:4])[0]
    if biSize not in (12, 40, 52, 56, 108, 124):
        return None
    
    try:
        if biSize >= 40:
            biWidth, biHeight, biPlanes, biBitCount, biCompression, biSizeImage, biXPelsPerMeter, biYPelsPerMeter, biClrUsed, biClrImportant = struct.unpack('<iiHHIIiiII', dib_data[4:40])
        else:
            biWidth, biHeight, biPlanes, biBitCount = struct.unpack('<HHHH', dib_data[4:12])
            biCompression = 0
            biClrUsed = 0

        w = abs(biWidth)
        h = abs(biHeight)

        if w == 0 or h == 0 or w > 10000 or h > 10000:
            return None

        # Cálculo de paleta de colores de Wilcom
        if biClrUsed > 0:
            num_colors = biClrUsed
        elif biBitCount <= 8:
            num_colors = 1 << biBitCount
        else:
            num_colors = 0

        entry_size = 3 if biSize == 12 else 4
        palette_size = num_colors * entry_size

        if biSize == 40 and biCompression in (3, 6):
            palette_size += 12

        # Cálculo de los bytes reales de los píxeles (sin basura del flujo OLE)
        if biSizeImage > 0:
            pixel_bytes_len = biSizeImage
        else:
            row_stride = ((w * biBitCount + 31) // 32) * 4
            pixel_bytes_len = row_stride * h

        total_dib_len = biSize + palette_size + pixel_bytes_len
        if total_dib_len > len(dib_data):
            total_dib_len = len(dib_data)

        actual_dib = dib_data[:total_dib_len]

        offset_to_pixels = 14 + biSize + palette_size
        file_size = 14 + len(actual_dib)

        file_header = struct.pack('<2sIHHI', b'BM', file_size, 0, 0, offset_to_pixels)
        return file_header + actual_dib
    except Exception:
        return None

def extract_image_from_stream(data):
    """Escaner profundo de firmas gráficas en los flujos binarios."""
    # 1. Búsqueda de PNG
    png_idx = data.find(b'\x89PNG\r\n\x1a\n')
    if png_idx != -1:
        try:
            img = Image.open(io.BytesIO(data[png_idx:]))
            if img.width > 0 and img.height > 0:
                return img
        except Exception:
            pass

    # 2. Búsqueda de JPG
    jpg_idx = data.find(b'\xFF\xD8\xFF')
    if jpg_idx != -1:
        try:
            img = Image.open(io.BytesIO(data[jpg_idx:]))
            if img.width > 0 and img.height > 0:
                return img
        except Exception:
            pass

    # 3. Búsqueda de BMP
    bmp_idx = 0
    while True:
        bmp_idx = data.find(b'BM', bmp_idx)
        if bmp_idx == -1:
            break
        try:
            img = Image.open(io.BytesIO(data[bmp_idx:]))
            if img.width > 0 and img.height > 0:
                return img
        except Exception:
            pass
        bmp_idx += 2

    # 4. Búsqueda de cabeceras DIB de Wilcom
    for signature in (b'\x28\x00\x00\x00', b'\x6C\x00\x00\x00', b'\x7C\x00\x00\x00', b'\x0C\x00\x00\x00'):
        pos = 0
        while True:
            pos = data.find(signature, pos)
            if pos == -1:
                break
            dib_candidate = data[pos:]
            bmp_bytes = dib_to_bmp(dib_candidate)
            if bmp_bytes:
                try:
                    img = Image.open(io.BytesIO(bmp_bytes))
                    if img.width > 0 and img.height > 0:
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

    # Nivel 1: Búsqueda en metadatos de Wilcom
    if olefile.isOleFile(file_io):
        try:
            ole = olefile.OleFileIO(file_io)
            meta = ole.get_metadata()
            if meta.thumbnail:
                img = extract_image_from_stream(meta.thumbnail)
                if img:
                    output_io = io.BytesIO()
                    img.save(output_io, 'PNG')
                    output_io.seek(0)
                    return send_file(output_io, mimetype='image/png')
            
            # Nivel 2: Búsqueda flujo por flujo
            for stream_path in ole.listdir():
                try:
                    stream_data = ole.openstream(stream_path).read()
                    img = extract_image_from_stream(stream_data)
                    if img:
                        output_io = io.BytesIO()
                        img.save(output_io, 'PNG')
                        output_io.seek(0)
                        return send_file(output_io, mimetype='image/png')
                except Exception:
                    continue
        except Exception:
            pass

    # Nivel 3: Escaneo crudo de la estructura binaria completa
    img = extract_image_from_stream(file_bytes)
    if img:
        output_io = io.BytesIO()
        img.save(output_io, 'PNG')
        output_io.seek(0)
        return send_file(output_io, mimetype='image/png')

    return "No se pudo extraer la vista previa del archivo EMB", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
