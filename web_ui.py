#!/usr/bin/env python3
"""
WSD Auto Drawer - Web UI
使用 Flask 构建 Web 界面
"""

import os
import tempfile
import uuid
from flask import Flask, render_template, request, send_file, jsonify

from svg_to_wsd import svg_to_wsd
from wsd_to_svg import wsd_to_svg

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 限制

# 临时文件目录
TEMP_DIR = tempfile.mkdtemp(prefix='wsd_web_')


@app.route('/')
def index():
    """首页"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/convert', methods=['POST'])
def convert():
    """转换 API"""
    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400
    
    file = request.files['file']
    mode = request.form.get('mode', 'svg2wsd')
    
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400
    
    # 保存上传文件
    input_ext = '.svg' if mode == 'svg2wsd' else '.wsd'
    output_ext = '.wsd' if mode == 'svg2wsd' else '.svg'
    
    unique_id = str(uuid.uuid4())[:8]
    input_path = os.path.join(TEMP_DIR, f"{unique_id}_input{input_ext}")
    output_path = os.path.join(TEMP_DIR, f"{unique_id}_output{output_ext}")
    
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
        # 清理临时文件
        if os.path.exists(input_path):
            os.remove(input_path)


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WSD Auto Drawer - 在线转换</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: "Microsoft YaHei", -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 500px;
            padding: 40px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #333;
            font-size: 28px;
            margin-bottom: 8px;
        }
        .header p {
            color: #666;
            font-size: 14px;
        }
        .mode-selector {
            display: flex;
            background: #f5f5f5;
            border-radius: 10px;
            padding: 4px;
            margin-bottom: 24px;
        }
        .mode-btn {
            flex: 1;
            padding: 12px;
            border: none;
            background: transparent;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            color: #666;
            transition: all 0.3s;
        }
        .mode-btn.active {
            background: #2196F3;
            color: white;
            box-shadow: 0 2px 8px rgba(33,150,243,0.3);
        }
        .upload-area {
            border: 2px dashed #ddd;
            border-radius: 12px;
            padding: 40px 20px;
            text-align: center;
            margin-bottom: 24px;
            transition: all 0.3s;
            cursor: pointer;
        }
        .upload-area:hover, .upload-area.dragover {
            border-color: #2196F3;
            background: #f0f7ff;
        }
        .upload-icon {
            font-size: 48px;
            margin-bottom: 12px;
        }
        .upload-text {
            color: #666;
            font-size: 14px;
            margin-bottom: 8px;
        }
        .upload-hint {
            color: #999;
            font-size: 12px;
        }
        #file-input {
            display: none;
        }
        .file-info {
            background: #e8f5e9;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 16px;
            display: none;
        }
        .file-info.show {
            display: block;
        }
        .convert-btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .convert-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102,126,234,0.4);
        }
        .convert-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .progress {
            display: none;
            margin-top: 16px;
            text-align: center;
        }
        .progress.show {
            display: block;
        }
        .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #2196F3;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 8px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .footer {
            text-align: center;
            margin-top: 24px;
            color: #999;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>WSD Auto Drawer</h1>
            <p>SVG 与 WSD 格式在线转换</p>
        </div>
        
        <div class="mode-selector">
            <button class="mode-btn active" data-mode="svg2wsd">SVG → WSD</button>
            <button class="mode-btn" data-mode="wsd2svg">WSD → SVG</button>
        </div>
        
        <form id="convert-form" action="/convert" method="post" enctype="multipart/form-data">
            <input type="hidden" name="mode" id="mode-input" value="svg2wsd">
            
            <div class="upload-area" id="upload-area">
                <div class="upload-icon">📁</div>
                <div class="upload-text">点击或拖拽文件到此处</div>
                <div class="upload-hint">支持 .svg 和 .wsd 格式</div>
                <input type="file" name="file" id="file-input" accept=".svg,.wsd">
            </div>
            
            <div class="file-info" id="file-info">
                <span id="filename"></span>
            </div>
            
            <button type="submit" class="convert-btn" id="convert-btn" disabled>开始转换</button>
        </form>
        
        <div class="progress" id="progress">
            <div class="spinner"></div>
            <p>正在转换...</p>
        </div>
        
        <div class="footer">
            <p>基于 EduEditor WStudio7 格式逆向工程</p>
        </div>
    </div>
    
    <script>
        const uploadArea = document.getElementById("upload-area");
        const fileInput = document.getElementById("file-input");
        const fileInfo = document.getElementById("file-info");
        const filename = document.getElementById("filename");
        const convertBtn = document.getElementById("convert-btn");
        const modeBtns = document.querySelectorAll(".mode-btn");
        const modeInput = document.getElementById("mode-input");
        const form = document.getElementById("convert-form");
        const progress = document.getElementById("progress");
        
        // 模式切换
        modeBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                modeBtns.forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                modeInput.value = btn.dataset.mode;
                
                // 更新接受的文件类型
                if (btn.dataset.mode === "svg2wsd") {
                    fileInput.accept = ".svg";
                } else {
                    fileInput.accept = ".wsd";
                }
            });
        });
        
        // 文件选择
        uploadArea.addEventListener("click", () => fileInput.click());
        
        fileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                filename.textContent = e.target.files[0].name;
                fileInfo.classList.add("show");
                convertBtn.disabled = false;
            }
        });
        
        // 拖拽上传
        uploadArea.addEventListener("dragover", (e) => {
            e.preventDefault();
            uploadArea.classList.add("dragover");
        });
        
        uploadArea.addEventListener("dragleave", () => {
            uploadArea.classList.remove("dragover");
        });
        
        uploadArea.addEventListener("drop", (e) => {
            e.preventDefault();
            uploadArea.classList.remove("dragover");
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files;
                filename.textContent = files[0].name;
                fileInfo.classList.add("show");
                convertBtn.disabled = false;
            }
        });
        
        // 表单提交
        form.addEventListener("submit", (e) => {
            convertBtn.disabled = true;
            progress.classList.add("show");
        });
    </script>
</body>
</html>
'''


def main():
    print("=" * 50)
    print("WSD Auto Drawer - Web UI")
    print("=" * 50)
    print(f"访问地址: http://127.0.0.1:5000")
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)


if __name__ == '__main__':
    main()
