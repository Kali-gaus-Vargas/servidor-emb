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
    
    try:
        ole = olefile.OleFileIO(file_bytes)
        
        preview_data = None
        for stream_name in ole.listdir():
            name = "/".join(stream_name)
            if "SummaryInformation" in name or "Contents" in name:
                data = ole.openstream(stream_name).read()
                match = re.search(b'(\xFF\xD8\xFF|\x89PNG|\x42\x4D)', data)
                if match:
                    preview_data = data[match.start():]
                    break
        
        if preview_data:
            img = Image.open(io.BytesIO(preview_data))
            output_io = io.BytesIO()
            img.save(output_io, 'PNG', quality=100)
            output_io.seek(0)
            return send_file(output_io, mimetype='image/png')
            
    except Exception as e:
        return str(e), 500

    return "No preview found in EMB", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
