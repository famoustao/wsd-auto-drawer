#!/usr/bin/env python3
"""
WSD Auto Drawer - Web UI (支持批量处理)
使用 Flask 构建 Web 界面
"""

import os
import io
import tempfile
import uuid
import zipfile
from flask import Flask, render_template_string, request, send_file, jsonify

from svg_to_wsd import svg_to_wsd
from wsd_to_svg import wsd_to_svg

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB

TEMP_DIR = tempfile.mkdtemp(prefix='wsd_web_')


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/convert', methods=['POST'])
def convert():
    """单文件转换"""
    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400

    file = request.files['file']
    mode = request.form.get('mode', 'svg2wsd')

    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400

    input_ext = '.svg' if mode == 'svg2wsd' else '.wsd'
    output_ext = '.wsd' if mode == 'svg2wsd' else '.svg'

    uid = str(uuid.uuid4())[:8]
    input_path = os.path.join(TEMP_DIR, f"{uid}_input{input_ext}")
    output_path = os.path.join(TEMP_DIR, f"{uid}_output{output_ext}")

    file.save(input_path)

    try:
        if mode == 'svg2wsd':
            svg_to_wsd(input_path, output_path)
        else:
            wsd_to_svg(input_path, output_path)

        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"converted{output_ext}"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)


@app.route('/batch_convert', methods=['POST'])
def batch_convert():
    """批量转换并打包 ZIP"""
    if 'files' not in request.files:
        return jsonify({'error': '未上传文件'}), 400

    files = request.files.getlist('files')
    mode = request.form.get('mode', 'svg2wsd')

    # 过滤空文件
    files = [f for f in files if f and f.filename]
    if not files:
        return jsonify({'error': '没有有效文件'}), 400

    input_ext = '.svg' if mode == 'svg2wsd' else '.wsd'
    output_ext = '.wsd' if mode == 'svg2wsd' else '.svg'

    results = []
    errors = []

    # 创建 ZIP 内存缓冲区
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            if not file.filename.lower().endswith(input_ext):
                errors.append(f"跳过非目标格式: {file.filename}")
                continue

            uid = str(uuid.uuid4())[:8]
            input_path = os.path.join(TEMP_DIR, f"{uid}_input{input_ext}")
            output_path = os.path.join(TEMP_DIR, f"{uid}_output{output_ext}")

            try:
                file.save(input_path)

                if mode == 'svg2wsd':
                    svg_to_wsd(input_path, output_path)
                else:
                    wsd_to_svg(input_path, output_path)

                # 写入 ZIP
                arcname = os.path.splitext(file.filename)[0] + output_ext
                zf.write(output_path, arcname)
                results.append(file.filename)

            except Exception as e:
                errors.append(f"{file.filename}: {str(e)}")

            finally:
                for p in (input_path, output_path):
                    if os.path.exists(p):
                        os.remove(p)

    if not results:
        return jsonify({'error': '所有文件转换失败', 'details': errors}), 500

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"wsd_batch_{mode}.zip"
    )


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WSD Auto Drawer - 批量转换</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body {
    font-family:"Microsoft YaHei",-apple-system,BlinkMacSystemFont,sans-serif;
    background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
    min-height:100vh; display:flex; justify-content:center; align-items:center;
    padding:20px;
}
.container {
    background:white; border-radius:16px;
    box-shadow:0 20px 60px rgba(0,0,0,0.3);
    width:100%; max-width:520px; padding:36px;
}
.header { text-align:center; margin-bottom:24px; }
.header h1 { color:#333; font-size:26px; margin-bottom:6px; }
.header p { color:#666; font-size:13px; }
.mode-selector {
    display:flex; background:#f5f5f5; border-radius:10px; padding:4px; margin-bottom:18px;
}
.mode-btn {
    flex:1; padding:10px; border:none; background:transparent;
    border-radius:8px; cursor:pointer; font-size:14px; font-weight:500;
    color:#666; transition:all .3s;
}
.mode-btn.active { background:#2196F3; color:white; box-shadow:0 2px 8px rgba(33,150,243,.3); }
.batch-toggle {
    display:flex; align-items:center; gap:8px; margin-bottom:16px;
    font-size:14px; color:#333; cursor:pointer;
}
.batch-toggle input { width:18px; height:18px; cursor:pointer; }
.upload-area {
    border:2px dashed #ddd; border-radius:12px; padding:32px 16px;
    text-align:center; margin-bottom:16px; transition:all .3s; cursor:pointer;
}
.upload-area:hover, .upload-area.dragover { border-color:#2196F3; background:#f0f7ff; }
.upload-icon { font-size:42px; margin-bottom:10px; }
.upload-text { color:#666; font-size:14px; margin-bottom:6px; }
.upload-hint { color:#999; font-size:12px; }
#file-input { display:none; }
.file-list {
    background:#e8f5e9; border-radius:8px; padding:10px 14px;
    margin-bottom:12px; display:none; max-height:120px; overflow-y:auto;
}
.file-list.show { display:block; }
.file-item { font-size:13px; color:#333; padding:2px 0; }
.convert-btn {
    width:100%; padding:13px;
    background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
    color:white; border:none; border-radius:10px;
    font-size:15px; font-weight:600; cursor:pointer; transition:all .3s;
}
.convert-btn:hover { transform:translateY(-2px); box-shadow:0 8px 20px rgba(102,126,234,.4); }
.convert-btn:disabled { opacity:.6; cursor:not-allowed; transform:none; }
.progress { display:none; margin-top:14px; text-align:center; }
.progress.show { display:block; }
.spinner {
    width:30px; height:30px; border:3px solid #f3f3f3;
    border-top:3px solid #2196F3; border-radius:50%;
    animation:spin 1s linear infinite; margin:0 auto 8px;
}
@keyframes spin { 0%{transform:rotate(0)} 100%{transform:rotate(360deg)} }
.footer { text-align:center; margin-top:18px; color:#999; font-size:12px; }
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>WSD Auto Drawer</h1>
        <p>SVG 与 WSD 格式批量转换</p>
    </div>

    <div class="mode-selector">
        <button class="mode-btn active" data-mode="svg2wsd">SVG → WSD</button>
        <button class="mode-btn" data-mode="wsd2svg">WSD → SVG</button>
    </div>

    <label class="batch-toggle">
        <input type="checkbox" id="batch-check">
        <span>批量模式（支持多文件，结果打包 ZIP）</span>
    </label>

    <div class="upload-area" id="upload-area">
        <div class="upload-icon">📁</div>
        <div class="upload-text" id="upload-text">点击或拖拽文件到此处</div>
        <div class="upload-hint" id="upload-hint">支持 .svg 和 .wsd 格式</div>
        <input type="file" name="file" id="file-input" accept=".svg,.wsd">
    </div>

    <div class="file-list" id="file-list"></div>

    <button class="convert-btn" id="convert-btn" disabled>开始转换</button>

    <div class="progress" id="progress">
        <div class="spinner"></div>
        <p id="progress-text">正在转换...</p>
    </div>

    <div class="footer">
        <p>基于 EduEditor WStudio7 格式逆向工程</p>
    </div>
</div>

<script>
const uploadArea = document.getElementById("upload-area");
const fileInput = document.getElementById("file-input");
const fileList = document.getElementById("file-list");
const convertBtn = document.getElementById("convert-btn");
const modeBtns = document.querySelectorAll(".mode-btn");
const modeInput = { value: "svg2wsd" };
const batchCheck = document.getElementById("batch-check");
const progress = document.getElementById("progress");
const progressText = document.getElementById("progress-text");
const uploadText = document.getElementById("upload-text");
const uploadHint = document.getElementById("upload-hint");

let selectedFiles = [];

modeBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        modeBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        modeInput.value = btn.dataset.mode;
        fileInput.accept = btn.dataset.mode === "svg2wsd" ? ".svg" : ".wsd";
        updateUploadHint();
    });
});

batchCheck.addEventListener("change", () => {
    fileInput.multiple = batchCheck.checked;
    updateUploadHint();
    resetFiles();
});

function updateUploadHint() {
    const ext = modeInput.value === "svg2wsd" ? "SVG" : "WSD";
    if (batchCheck.checked) {
        uploadText.textContent = "点击或拖拽多个 " + ext + " 文件到此处";
        uploadHint.textContent = "批量模式: 所有结果将打包为 ZIP 下载";
    } else {
        uploadText.textContent = "点击或拖拽文件到此处";
        uploadHint.textContent = "支持 .svg 和 .wsd 格式";
    }
}

function resetFiles() {
    selectedFiles = [];
    fileInput.value = "";
    fileList.innerHTML = "";
    fileList.classList.remove("show");
    convertBtn.disabled = true;
}

function renderFileList() {
    fileList.innerHTML = "";
    selectedFiles.forEach(f => {
        const div = document.createElement("div");
        div.className = "file-item";
        div.textContent = "• " + f.name;
        fileList.appendChild(div);
    });
    fileList.classList.add("show");
}

uploadArea.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
        selectedFiles = Array.from(e.target.files);
        renderFileList();
        convertBtn.disabled = false;
    }
});

uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadArea.classList.add("dragover");
});
uploadArea.addEventListener("dragleave", () => uploadArea.classList.remove("dragover"));
uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadArea.classList.remove("dragover");
    const files = Array.from(e.dataTransfer.files).filter(f => {
        const ext = modeInput.value === "svg2wsd" ? ".svg" : ".wsd";
        return f.name.toLowerCase().endsWith(ext);
    });
    if (files.length > 0) {
        selectedFiles = files;
        renderFileList();
        convertBtn.disabled = false;
    }
});

convertBtn.addEventListener("click", async () => {
    if (selectedFiles.length === 0) return;

    convertBtn.disabled = true;
    progress.classList.add("show");
    progressText.textContent = batchCheck.checked
        ? "正在批量转换并打包 ZIP..."
        : "正在转换...";

    const formData = new FormData();
    formData.append("mode", modeInput.value);

    const isBatch = batchCheck.checked;
    const url = isBatch ? "/batch_convert" : "/convert";

    if (isBatch) {
        selectedFiles.forEach(f => formData.append("files", f));
    } else {
        formData.append("file", selectedFiles[0]);
    }

    try {
        const res = await fetch(url, { method: "POST", body: formData });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || "转换失败");
        }
        const blob = await res.blob();
        const dlUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = dlUrl;
        a.download = isBatch ? "wsd_batch_" + modeInput.value + ".zip" : "converted" + (modeInput.value === "svg2wsd" ? ".wsd" : ".svg");
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(dlUrl);
        progressText.textContent = "下载已开始";
    } catch (e) {
        progressText.textContent = "错误: " + e.message;
    } finally {
        setTimeout(() => {
            convertBtn.disabled = false;
            progress.classList.remove("show");
        }, 1500);
    }
});
</script>
</body>
</html>
'''


def main():
    print("=" * 50)
    print("WSD Auto Drawer - Web UI (批量支持)")
    print("=" * 50)
    print("访问地址: http://127.0.0.1:5000")
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)


if __name__ == '__main__':
    main()
