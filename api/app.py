from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_socketio import SocketIO, emit
import requests
import json
import os
import uuid
import time
import threading
from datetime import datetime
from PIL import Image
import io
import cv2
import shutil
from database import Database

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Favicon route: prefer an existing ICO, otherwise convert PNG to ICO on the fly
@app.route('/favicon.ico')
def favicon():
    try:
        ico_path = os.path.join('static', 'favicon.ico')
        if os.path.exists(ico_path):
            return send_file(ico_path, mimetype='image/x-icon')

        png_path = os.path.join('static', 'favicon.png')
        if os.path.exists(png_path):
            img = Image.open(png_path).convert('RGBA')
            sizes = [(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
            buf = io.BytesIO()
            img.save(buf, format='ICO', sizes=sizes)
            buf.seek(0)
            return send_file(buf, mimetype='image/x-icon')

        return ('', 204)
    except Exception:
        return ('', 204)

# 添加模板過濾器
@app.template_filter('datetime_format')
def datetime_format(value):
    """格式化日期時間"""
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    else:
        dt = value
    return dt.strftime('%Y-%m-%d %H:%M:%S')

@app.template_filter('parse_datetime')
def parse_datetime(value):
    """解析日期時間字符串"""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return datetime.now()
    return value

# 設定
COMFYUI_HOST = os.getenv('COMFYUI_HOST', 'host.docker.internal')
COMFYUI_PORT = os.getenv('COMFYUI_PORT', '8188')
COMFYUI_URL = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"
DATABASE_PATH = os.getenv('DATABASE_PATH', '/app/database/history.db')

# 初始化資料庫
db = Database(DATABASE_PATH)

# 載入工作流程模板
with open('/app/workflow.json', 'r', encoding='utf-8') as f:
    WORKFLOW_TEMPLATE = json.load(f)

# 載入首尾幀工作流程模板
with open('/app/workflow_first_last.json', 'r', encoding='utf-8') as f:
    WORKFLOW_FIRST_LAST_TEMPLATE = json.load(f)

class ComfyUIClient:
    def __init__(self, base_url):
        self.base_url = base_url
    
    def queue_prompt(self, workflow):
        """提交工作流程到ComfyUI"""
        try:
            response = requests.post(f"{self.base_url}/prompt", json={"prompt": workflow})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error queuing prompt: {e}")
            return None
    
    def get_queue_status(self):
        """獲取ComfyUI排隊狀態"""
        try:
            response = requests.get(f"{self.base_url}/queue")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting queue status: {e}")
            return None
    
    def get_history(self, prompt_id=None):
        """獲取歷史記錄"""
        try:
            url = f"{self.base_url}/history"
            if prompt_id:
                url += f"/{prompt_id}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting history: {e}")
            return None
    
    def get_image(self, filename, subfolder="", folder_type="output"):
        """獲取生成的圖片/影片"""
        try:
            params = {
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type
            }
            response = requests.get(f"{self.base_url}/view", params=params)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Error getting image: {e}")
            return None

comfyui_client = ComfyUIClient(COMFYUI_URL)

def create_workflow(prompt, image_filename, width, height, duration):
    """根據參數建立工作流程"""
    import copy
    workflow = copy.deepcopy(WORKFLOW_TEMPLATE)
    
    # 更新參數
    workflow["6"]["inputs"]["text"] = prompt  # 提示詞
    workflow["52"]["inputs"]["image"] = image_filename  # 圖片檔名
    workflow["75"]["inputs"]["value"] = width  # 寬度
    workflow["76"]["inputs"]["value"] = height  # 高度
    workflow["77"]["inputs"]["value"] = duration  # 時長
    
    
    # 確保有輸出節點 - 將節點63標記為輸出
    if "63" in workflow:
        workflow["63"]["_meta"]["save_output"] = True
    
    return workflow

def create_first_last_workflow(prompt, first_image_filename, last_image_filename, width, height, duration):
    """根據參數建立首尾幀工作流程"""
    import copy
    workflow = copy.deepcopy(WORKFLOW_FIRST_LAST_TEMPLATE)
    
    # 更新參數
    workflow["22"]["inputs"]["text"] = prompt  # 提示詞
    workflow["12"]["inputs"]["image"] = first_image_filename  # 首幀圖片
    workflow["28"]["inputs"]["image"] = last_image_filename  # 尾幀圖片
    workflow["33"]["inputs"]["value"] = width  # 寬度
    workflow["34"]["inputs"]["value"] = height  # 高度
    workflow["35"]["inputs"]["value"] = duration  # 時長
    
    # 確保有輸出節點 - 將節點6標記為輸出
    if "6" in workflow:
        workflow["6"]["_meta"]["save_output"] = True
    
    return workflow

def generate_thumbnail(video_path, thumbnail_path):
    """生成影片縮圖"""
    try:
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if ret:
            # 調整縮圖大小
            height, width = frame.shape[:2]
            aspect_ratio = width / height
            if aspect_ratio > 1:
                new_width = 320
                new_height = int(320 / aspect_ratio)
            else:
                new_height = 320
                new_width = int(320 * aspect_ratio)
            
            resized_frame = cv2.resize(frame, (new_width, new_height))
            cv2.imwrite(thumbnail_path, resized_frame)
            cap.release()
            return True
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
    return False

def monitor_task(task_id, prompt_id):
    """監控任務進度"""
    max_attempts = 1800  # 最多等待30分鐘
    attempt = 0
    
    while attempt < max_attempts:
        try:
            # 檢查ComfyUI歷史記錄
            history = comfyui_client.get_history(prompt_id)
            print(f"[DEBUG] Task {task_id}: Checking history for prompt_id {prompt_id}")
            
            if history and prompt_id in history:
                task_info = history[prompt_id]
                print(f"[DEBUG] Task {task_id}: Found task info in history")
                
                if 'outputs' in task_info:
                    # 任務完成
                    outputs = task_info['outputs']
                    print(f"[DEBUG] Task {task_id}: Found outputs: {list(outputs.keys())}")
                    
                    # 尋找影片輸出
                    video_filename = None
                    for node_id, output in outputs.items():
                        print(f"[DEBUG] Task {task_id}: Checking node {node_id}: {list(output.keys())}")
                        if 'gifs' in output and output['gifs']:
                            video_filename = output['gifs'][0]['filename']
                            print(f"[DEBUG] Task {task_id}: Found gif output: {video_filename}")
                            break
                        elif 'videos' in output and output['videos']:
                            video_filename = output['videos'][0]['filename']
                            print(f"[DEBUG] Task {task_id}: Found video output: {video_filename}")
                            break
                    
                    if video_filename:
                        # 檢查ComfyUI輸出目錄中的影片檔案
                        # 首先嘗試掛載的目錄
                        comfyui_video_path = f"/app/comfyui_output/{video_filename}"
                        # 如果掛載目錄不存在，嘗試直接路徑
                        if not os.path.exists(comfyui_video_path):
                            comfyui_video_path = f"/home/hank/comfy/ComfyUI/output/{video_filename}"
                        
                        output_path = f"/app/output/{task_id}_{video_filename}"
                        
                        video_processed = False
                        
                        if os.path.exists(comfyui_video_path):
                            # 複製影片檔案到我們的輸出目錄
                            shutil.copy2(comfyui_video_path, output_path)
                            video_processed = True
                            print(f"Video file copied from {comfyui_video_path} to {output_path}")
                        else:
                            # 如果檔案不存在，嘗試使用API下載
                            video_content = comfyui_client.get_image(video_filename)
                            if video_content:
                                with open(output_path, 'wb') as f:
                                    f.write(video_content)
                                video_processed = True
                                print(f"Video file downloaded via API: {video_filename}")
                            else:
                                print(f"Failed to get video file: {video_filename}")
                        
                        if video_processed:
                            # 生成縮圖
                            thumbnail_filename = f"{task_id}_thumb.jpg"
                            thumbnail_path = f"/app/thumbnails/{thumbnail_filename}"
                            generate_thumbnail(output_path, thumbnail_path)
                            
                            # 更新資料庫
                            db.update_task_status(
                                task_id, 
                                'completed',
                                output_filename=f"{task_id}_{video_filename}",
                                thumbnail_filename=thumbnail_filename
                            )
                            
                            # 發送WebSocket通知
                            socketio.emit('task_completed', {
                                'task_id': task_id,
                                'status': 'completed',
                                'output_filename': f"{task_id}_{video_filename}",
                                'thumbnail_filename': thumbnail_filename
                            })
                            
                            # 處理下一個排隊中的任務
                            process_next_task()
                            
                            return
                    else:
                        print(f"[DEBUG] Task {task_id}: No video filename found in outputs")
                        # 備用檢測：掃描ComfyUI輸出目錄中的最新文件
                        try:
                            comfyui_output_dir = "/home/hank/comfy/ComfyUI/output"
                            if os.path.exists(comfyui_output_dir):
                                # 獲取所有wan22開頭的mp4文件，按修改時間排序
                                output_files = []
                                for filename in os.listdir(comfyui_output_dir):
                                    if filename.startswith('wan22__') and filename.endswith('.mp4'):
                                        filepath = os.path.join(comfyui_output_dir, filename)
                                        mtime = os.path.getmtime(filepath)
                                        output_files.append((filename, mtime, filepath))
                                
                                # 按修改時間排序，最新的在前
                                output_files.sort(key=lambda x: x[1], reverse=True)
                                
                                if output_files:
                                    latest_file = output_files[0]
                                    # 檢查文件是否在任務開始後創建
                                    task_start_time = time.time() - (attempt * 2)  # 估算任務開始時間
                                    if latest_file[1] > task_start_time:
                                        video_filename = latest_file[0]
                                        output_path = f"/app/output/{task_id}_{video_filename}"
                                        
                                        # 複製文件
                                        shutil.copy2(latest_file[2], output_path)
                                        print(f"[BACKUP] Video file copied from {latest_file[2]} to {output_path}")
                                        
                                        # 生成縮圖
                                        thumbnail_filename = f"{task_id}_thumb.jpg"
                                        thumbnail_path = f"/app/thumbnails/{thumbnail_filename}"
                                        generate_thumbnail(output_path, thumbnail_path)
                                        
                                        # 更新資料庫
                                        db.update_task_status(
                                            task_id, 
                                            'completed',
                                            output_filename=f"{task_id}_{video_filename}",
                                            thumbnail_filename=thumbnail_filename
                                        )
                                        
                                        # 發送WebSocket通知
                                        socketio.emit('task_completed', {
                                            'task_id': task_id,
                                            'status': 'completed',
                                            'output_filename': f"{task_id}_{video_filename}",
                                            'thumbnail_filename': thumbnail_filename
                                        })
                                        
                                        return
                        except Exception as backup_e:
                            print(f"[DEBUG] Backup detection failed: {backup_e}")
                
                elif 'status' in task_info and task_info['status'].get('completed', False):
                    # 檢查是否有錯誤
                    if 'status' in task_info and 'messages' in task_info['status']:
                        error_msg = str(task_info['status']['messages'])
                        db.update_task_status(task_id, 'failed', error_message=error_msg)
                        socketio.emit('task_failed', {
                            'task_id': task_id,
                            'error': error_msg
                        })
                        
                        # 處理下一個排隊中的任務
                        process_next_task()
                        
                        return
            
            # 檢查排隊狀態
            queue_status = comfyui_client.get_queue_status()
            if queue_status:
                # 發送排隊狀態更新
                socketio.emit('queue_update', queue_status)
            
            time.sleep(2)
            attempt += 1
            
        except Exception as e:
            print(f"Error monitoring task {task_id}: {e}")
            time.sleep(5)
            attempt += 1
    
    # 超時
    db.update_task_status(task_id, 'failed', error_message='任務超時')
    socketio.emit('task_failed', {
        'task_id': task_id,
        'error': '任務超時'
    })
    
    # 處理下一個排隊中的任務
    process_next_task()

@app.route('/')
def index():
    """主頁面"""
    try:
        # 獲取本地排隊狀態
        local_queue = db.get_queue_status()
        
        # 獲取ComfyUI排隊狀態
        comfyui_queue = comfyui_client.get_queue_status()
        
        # 獲取最近5個任務
        recent_tasks = db.get_all_tasks(limit=5)
        
        return render_template('index.html', 
                             local_queue=local_queue,
                             comfyui_queue=comfyui_queue,
                             recent_tasks=recent_tasks)
    except Exception as e:
        print(f"Error in index: {e}")
        # 返回基本頁面
        return render_template('index.html', 
                             local_queue=None,
                             comfyui_queue=None,
                             recent_tasks=[])

@app.route('/history')
def history():
    """歷史記錄頁面"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    # 每頁顯示9個任務
    limit = 9
    offset = (page - 1) * limit
    
    # 獲取任務和總數
    if search:
        tasks = db.search_tasks(search, limit, offset)
        total_count = db.count_tasks(status if status else None, search)
    else:
        tasks = db.get_all_tasks(limit, offset, status if status else None)
        total_count = db.count_tasks(status if status else None)
    
    # 計算總頁數
    import math
    total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
    
    # 計算分頁範圍
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    
    return render_template('history.html', 
                         tasks=tasks, 
                         page=page, 
                         search=search, 
                         status=status,
                         total_count=total_count,
                         total_pages=total_pages,
                         start_page=start_page,
                         end_page=end_page)

@app.route('/task/<task_id>')
def task_detail(task_id):
    """任務詳細頁面"""
    task = db.get_task(task_id)
    if not task:
        return "任務不存在", 404
    return render_template('detail.html', task=task)

@app.route('/queue')
def queue_status():
    """排隊狀態頁面"""
    try:
        # 獲取本地排隊狀態
        local_queue = db.get_queue_status()
        
        # 獲取ComfyUI排隊狀態
        comfyui_queue = comfyui_client.get_queue_status()
        
        # 獲取處理中和排隊中的任務
        processing_tasks = db.get_all_tasks(status='processing')
        pending_tasks = db.get_all_tasks(status='pending')
        
        # 計算等待時間
        wait_times = calculate_estimated_wait_time(pending_tasks, processing_tasks)
        
        # 將等待時間添加到任務資料中
        wait_time_dict = {wt['task_id']: wt['wait_time_minutes'] for wt in wait_times}
        for task in pending_tasks:
            task['estimated_wait_time'] = wait_time_dict.get(task['task_id'], 0)
        
        # 獲取當前時間
        now = datetime.now()
        
        return render_template('queue.html', 
                             local_queue=local_queue,
                             comfyui_queue=comfyui_queue,
                             processing_tasks=processing_tasks,
                             pending_tasks=pending_tasks,
                             now=now)
    except Exception as e:
        print(f"Error in queue_status: {e}")
        # 返回錯誤頁面或基本資訊
        return render_template('queue.html', 
                             local_queue=None,
                             comfyui_queue=None,
                             processing_tasks=[],
                             pending_tasks=[],
                             now=datetime.now())

@app.route('/api/generate', methods=['POST'])
def generate_video():
    """生成影片API"""
    try:
        # 獲取參數
        prompt = request.form.get('prompt', '').strip()
        width = int(request.form.get('width', 480))
        height = int(request.form.get('height', 832))
        duration = int(request.form.get('duration', 81))  # 改為預設5秒
        generation_mode = request.form.get('mode', 'single')  # 生成模式
        
        if not prompt:
            return jsonify({'error': '請輸入提示詞'}), 400
        
        # 生成任務ID
        task_id = str(uuid.uuid4())
        
        if generation_mode == 'single':
            # 單圖模式
            if 'image' not in request.files:
                return jsonify({'error': '請上傳圖片'}), 400
            
            image_file = request.files['image']
            if image_file.filename == '':
                return jsonify({'error': '請選擇圖片檔案'}), 400
            
            # 儲存上傳的圖片到本地input目錄
            image_filename = f"{task_id}_{image_file.filename}"
            image_path = f"/app/input/{image_filename}"
            image_file.save(image_path)
            
            # 同時複製到ComfyUI的input目錄
            comfyui_image_path = f"/app/comfyui_input/{image_filename}"
            shutil.copy2(image_path, comfyui_image_path)
            
            # 儲存到資料庫，初始狀態為pending
            db.add_task(task_id, prompt, image_filename, width, height, duration, generation_mode)
            
            # 檢查是否有正在處理的任務
            processing_tasks = db.get_all_tasks(status='processing')
            
            if len(processing_tasks) == 0:
                # 沒有正在處理的任務，可以立即開始處理
                return start_task_processing(task_id, prompt, image_filename, width, height, duration, generation_mode)
            else:
                # 有任務正在處理，保持pending狀態
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'message': '任務已加入排隊，等待處理中...',
                    'status': 'pending'
                })
        
        elif generation_mode == 'first_last':
            # 首尾幀模式
            if 'first_image' not in request.files or 'last_image' not in request.files:
                return jsonify({'error': '請上傳首幀和尾幀圖片'}), 400
            
            first_image_file = request.files['first_image']
            last_image_file = request.files['last_image']
            
            if first_image_file.filename == '' or last_image_file.filename == '':
                return jsonify({'error': '請選擇首幀和尾幀圖片檔案'}), 400
            
            # 儲存首幀圖片
            first_image_filename = f"{task_id}_first_{first_image_file.filename}"
            first_image_path = f"/app/input/{first_image_filename}"
            first_image_file.save(first_image_path)
            
            # 儲存尾幀圖片
            last_image_filename = f"{task_id}_last_{last_image_file.filename}"
            last_image_path = f"/app/input/{last_image_filename}"
            last_image_file.save(last_image_path)
            
            # 複製到ComfyUI的input目錄
            comfyui_first_image_path = f"/app/comfyui_input/{first_image_filename}"
            comfyui_last_image_path = f"/app/comfyui_input/{last_image_filename}"
            shutil.copy2(first_image_path, comfyui_first_image_path)
            shutil.copy2(last_image_path, comfyui_last_image_path)
            
            # 儲存到資料庫，初始狀態為pending
            db.add_task(task_id, prompt, first_image_filename, width, height, duration, generation_mode, last_image_filename)
            
            # 檢查是否有正在處理的任務
            processing_tasks = db.get_all_tasks(status='processing')
            
            if len(processing_tasks) == 0:
                # 沒有正在處理的任務，可以立即開始處理
                return start_task_processing_first_last(task_id, prompt, first_image_filename, last_image_filename, width, height, duration, generation_mode)
            else:
                # 有任務正在處理，保持pending狀態
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'message': '任務已加入排隊，等待處理中...',
                    'status': 'pending'
                })
        
        else:
            return jsonify({'error': '無效的生成模式'}), 400
        
    except Exception as e:
        print(f"Error in generate_video: {e}")
        return jsonify({'error': f'伺服器錯誤: {str(e)}'}), 500

def start_task_processing(task_id, prompt, image_filename, width, height, duration, generation_mode='single'):
    """開始處理任務"""
    try:
        # 建立工作流程
        workflow = create_workflow(prompt, image_filename, width, height, duration)
        
        # 提交到ComfyUI
        result = comfyui_client.queue_prompt(workflow)
        if not result:
            db.update_task_status(task_id, 'failed', error_message='ComfyUI連接失敗')
            return jsonify({'error': 'ComfyUI連接失敗'}), 500
        
        prompt_id = result.get('prompt_id')
        if not prompt_id:
            db.update_task_status(task_id, 'failed', error_message='提交任務失敗')
            return jsonify({'error': '提交任務失敗'}), 500
        
        # 更新狀態為processing
        db.update_task_status(task_id, 'processing', comfyui_prompt_id=prompt_id)
        
        # 啟動監控線程
        monitor_thread = threading.Thread(target=monitor_task, args=(task_id, prompt_id))
        monitor_thread.daemon = True
        monitor_thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'prompt_id': prompt_id,
            'message': '任務已提交，正在處理中...',
            'status': 'processing'
        })
        
    except Exception as e:
        print(f"Error starting task processing: {e}")
        db.update_task_status(task_id, 'failed', error_message=f'啟動處理失敗: {str(e)}')
        return jsonify({'error': f'啟動處理失敗: {str(e)}'}), 500

def start_task_processing_first_last(task_id, prompt, first_image_filename, last_image_filename, width, height, duration, generation_mode='first_last'):
    """開始處理首尾幀任務"""
    try:
        # 建立首尾幀工作流程
        workflow = create_first_last_workflow(prompt, first_image_filename, last_image_filename, width, height, duration)
        
        # 提交到ComfyUI
        result = comfyui_client.queue_prompt(workflow)
        if not result:
            db.update_task_status(task_id, 'failed', error_message='ComfyUI連接失敗')
            return jsonify({'error': 'ComfyUI連接失敗'}), 500
        
        prompt_id = result.get('prompt_id')
        if not prompt_id:
            db.update_task_status(task_id, 'failed', error_message='提交任務失敗')
            return jsonify({'error': '提交任務失敗'}), 500
        
        # 更新狀態為processing
        db.update_task_status(task_id, 'processing', comfyui_prompt_id=prompt_id)
        
        # 啟動監控線程
        monitor_thread = threading.Thread(target=monitor_task, args=(task_id, prompt_id))
        monitor_thread.daemon = True
        monitor_thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'prompt_id': prompt_id,
            'message': '首尾幀任務已提交，正在處理中...',
            'status': 'processing'
        })
        
    except Exception as e:
        print(f"Error starting first_last task processing: {e}")
        db.update_task_status(task_id, 'failed', error_message=f'啟動處理失敗: {str(e)}')
        return jsonify({'error': f'啟動處理失敗: {str(e)}'}), 500

def start_task_processing_internal(task_id, prompt, image_filename, width, height, duration):
    """內部使用的開始處理任務函數（不返回Flask響應）"""
    try:
        # 建立工作流程
        workflow = create_workflow(prompt, image_filename, width, height, duration)
        
        # 提交到ComfyUI
        result = comfyui_client.queue_prompt(workflow)
        if not result:
            db.update_task_status(task_id, 'failed', error_message='ComfyUI連接失敗')
            return False
        
        prompt_id = result.get('prompt_id')
        if not prompt_id:
            db.update_task_status(task_id, 'failed', error_message='提交任務失敗')
            return False
        
        # 更新狀態為processing
        db.update_task_status(task_id, 'processing', comfyui_prompt_id=prompt_id)
        
        # 啟動監控線程
        monitor_thread = threading.Thread(target=monitor_task, args=(task_id, prompt_id))
        monitor_thread.daemon = True
        monitor_thread.start()
        
        print(f"Task {task_id} started processing with prompt_id {prompt_id}")
        return True
        
    except Exception as e:
        print(f"Error starting task processing: {e}")
        db.update_task_status(task_id, 'failed', error_message=f'啟動處理失敗: {str(e)}')
        return False

def start_task_processing_first_last_internal(task_id, prompt, first_image_filename, last_image_filename, width, height, duration, generation_mode='first_last'):
    """內部使用的開始處理首尾幀任務函數（不返回Flask響應）"""
    try:
        # 建立首尾幀工作流程
        workflow = create_first_last_workflow(prompt, first_image_filename, last_image_filename, width, height, duration)
        
        # 提交到ComfyUI
        result = comfyui_client.queue_prompt(workflow)
        if not result:
            db.update_task_status(task_id, 'failed', error_message='ComfyUI連接失敗')
            return False
        
        prompt_id = result.get('prompt_id')
        if not prompt_id:
            db.update_task_status(task_id, 'failed', error_message='提交任務失敗')
            return False
        
        # 更新狀態為processing
        db.update_task_status(task_id, 'processing', comfyui_prompt_id=prompt_id)
        
        # 啟動監控線程
        monitor_thread = threading.Thread(target=monitor_task, args=(task_id, prompt_id))
        monitor_thread.daemon = True
        monitor_thread.start()
        
        print(f"First-last task {task_id} started processing with prompt_id {prompt_id}")
        return True
        
    except Exception as e:
        print(f"Error starting first_last task processing: {e}")
        db.update_task_status(task_id, 'failed', error_message=f'啟動處理失敗: {str(e)}')
        return False

def calculate_estimated_wait_time(pending_tasks, processing_tasks):
    """計算預估等待時間"""
    # 處理時間常數（分鐘）
    PROCESSING_TIME = {
        81: 4,   # 5秒影片需要4分鐘
        129: 7   # 8秒影片需要7分鐘
    }
    
    total_wait_time = 0
    
    # 計算當前處理中任務的剩餘時間
    if processing_tasks:
        current_task = processing_tasks[0]
        duration = current_task.get('duration', 81)
        processing_time = PROCESSING_TIME.get(duration, 4)
        
        # 計算已處理時間
        if current_task.get('started_at'):
            try:
                started_time = datetime.fromisoformat(current_task['started_at'].replace('Z', '+00:00'))
                elapsed_minutes = (datetime.now() - started_time).total_seconds() / 60
                remaining_time = max(0, processing_time - elapsed_minutes)
                total_wait_time += remaining_time
            except:
                # 如果無法解析時間，使用預設剩餘時間
                total_wait_time += processing_time / 2  # 假設已處理一半
        else:
            total_wait_time += processing_time
    
    # 為每個排隊任務添加等待時間
    wait_times = []
    for i, task in enumerate(pending_tasks):
        duration = task.get('duration', 81)
        task_processing_time = PROCESSING_TIME.get(duration, 4)
        
        # 當前任務的等待時間 = 前面所有任務的處理時間總和
        task_wait_time = total_wait_time
        wait_times.append({
            'task_id': task['task_id'],
            'wait_time_minutes': round(task_wait_time, 1)
        })
        
        # 累加這個任務的處理時間到總等待時間
        total_wait_time += task_processing_time
    
    return wait_times

def process_next_task():
    """處理下一個排隊中的任務"""
    try:
        with app.app_context():
            # 獲取最早的pending任務
            pending_tasks = db.get_all_tasks(status='pending', limit=1)
            
            if pending_tasks:
                task = pending_tasks[0]
                task_id = task['task_id']
                generation_mode = task.get('generation_mode', 'single')
                
                print(f"Starting next task: {task_id} (mode: {generation_mode})")
                
                if generation_mode == 'first_last':
                    # 首尾幀模式
                    success = start_task_processing_first_last_internal(
                        task_id,
                        task['prompt'],
                        task['image_filename'],  # 首幀圖片
                        task['second_image_filename'],  # 尾幀圖片
                        task['width'],
                        task['height'],
                        task['duration'],
                        generation_mode
                    )
                else:
                    # 單圖模式
                    success = start_task_processing_internal(
                        task_id,
                        task['prompt'],
                        task['image_filename'],
                        task['width'],
                        task['height'],
                        task['duration']
                    )
                
                if success:
                    print(f"Successfully started processing task {task_id}")
                else:
                    print(f"Failed to start processing task {task_id}")
            
    except Exception as e:
        print(f"Error processing next task: {e}")

@app.route('/api/task/<task_id>')
def get_task_status(task_id):
    """獲取任務狀態API"""
    task = db.get_task(task_id)
    if not task:
        return jsonify({'error': '任務不存在'}), 404
    return jsonify(task)

@app.route('/api/queue')
def get_queue_status_api():
    """獲取排隊狀態API"""
    local_queue = db.get_queue_status()
    comfyui_queue = comfyui_client.get_queue_status()
    
    return jsonify({
        'local_queue': local_queue,
        'comfyui_queue': comfyui_queue
    })

@app.route('/download/<filename>')
def download_file(filename):
    """下載檔案"""
    file_path = f"/app/output/{filename}"
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "檔案不存在", 404

@app.route('/video/<filename>')
def serve_video(filename):
    """提供影片檔案"""
    file_path = f"/app/output/{filename}"
    if os.path.exists(file_path):
        return send_file(file_path)
    return "檔案不存在", 404

@app.route('/thumbnail/<filename>')
def serve_thumbnail(filename):
    """提供縮圖檔案"""
    file_path = f"/app/thumbnails/{filename}"
    if os.path.exists(file_path):
        return send_file(file_path)
    return "檔案不存在", 404

@app.route('/input/<filename>')
def serve_input_image(filename):
    """提供輸入圖片檔案"""
    file_path = f"/app/input/{filename}"
    if os.path.exists(file_path):
        return send_file(file_path)
    return "檔案不存在", 404

@app.route('/api/recover-stuck-tasks', methods=['POST'])
def recover_stuck_tasks():
    """手動恢復卡住的任務API"""
    try:
        # 查找處理中的任務
        processing_tasks = db.get_all_tasks(status='processing')
        recovered_count = 0
        
        for task in processing_tasks:
            task_id = task['task_id']
            
            # 查找ComfyUI輸出目錄中最新的文件
            try:
                comfyui_output_dir = "/home/hank/comfy/ComfyUI/output"
                if os.path.exists(comfyui_output_dir):
                    # 獲取所有wan22開頭的mp4文件，按修改時間排序
                    output_files = []
                    for filename in os.listdir(comfyui_output_dir):
                        if filename.startswith('wan22__') and filename.endswith('.mp4'):
                            filepath = os.path.join(comfyui_output_dir, filename)
                            mtime = os.path.getmtime(filepath)
                            output_files.append((filename, mtime, filepath))
                    
                    # 按修改時間排序，最新的在前
                    output_files.sort(key=lambda x: x[1], reverse=True)
                    
                    if output_files:
                        # 檢查是否已經有對應的輸出文件
                        expected_output = f"{task_id}_{output_files[0][0]}"
                        output_path = f"/app/output/{expected_output}"
                        
                        if not os.path.exists(output_path):
                            # 複製最新的文件
                            latest_file = output_files[0]
                            shutil.copy2(latest_file[2], output_path)
                        
                        # 生成縮圖
                        thumbnail_filename = f"{task_id}_thumb.jpg"
                        thumbnail_path = f"/app/thumbnails/{thumbnail_filename}"
                        generate_thumbnail(output_path, thumbnail_path)
                        
                        # 更新資料庫
                        db.update_task_status(
                            task_id, 
                            'completed',
                            output_filename=expected_output,
                            thumbnail_filename=thumbnail_filename
                        )
                        
                        # 發送WebSocket通知
                        socketio.emit('task_completed', {
                            'task_id': task_id,
                            'status': 'completed',
                            'output_filename': expected_output,
                            'thumbnail_filename': thumbnail_filename
                        })
                        
                        recovered_count += 1
                        
            except Exception as e:
                print(f"Error recovering task {task_id}: {e}")
        
        return jsonify({
            'success': True,
            'message': f'已恢復 {recovered_count} 個卡住的任務',
            'recovered_count': recovered_count
        })
        
    except Exception as e:
        print(f"Error in recover_stuck_tasks: {e}")
        return jsonify({'error': f'恢復失敗: {str(e)}'}), 500

@app.route('/api/delete/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """刪除任務API"""
    try:
        # 從資料庫獲取任務資訊並刪除記錄
        task = db.delete_task(task_id)
        
        if not task:
            return jsonify({'error': '任務不存在'}), 404
        
        deleted_files = []
        
        # 刪除輸出影片檔案
        if task.get('output_filename'):
            output_path = f"/app/output/{task['output_filename']}"
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    deleted_files.append(task['output_filename'])
                except Exception as e:
                    print(f"Error deleting output file {output_path}: {e}")
        
        # 刪除縮圖檔案
        if task.get('thumbnail_filename'):
            thumbnail_path = f"/app/thumbnails/{task['thumbnail_filename']}"
            if os.path.exists(thumbnail_path):
                try:
                    os.remove(thumbnail_path)
                    deleted_files.append(task['thumbnail_filename'])
                except Exception as e:
                    print(f"Error deleting thumbnail file {thumbnail_path}: {e}")
        
        return jsonify({
            'success': True,
            'message': '任務已刪除',
            'deleted_files': deleted_files
        })
        
    except Exception as e:
        print(f"Error deleting task {task_id}: {e}")
        return jsonify({'error': f'刪除失敗: {str(e)}'}), 500

@socketio.on('connect')
def handle_connect():
    """WebSocket連接"""
    print('Client connected')
    emit('connected', {'message': '已連接到伺服器'})

@socketio.on('disconnect')
def handle_disconnect():
    """WebSocket斷開連接"""
    print('Client disconnected')

if __name__ == '__main__':
    # 確保目錄存在
    os.makedirs('/app/input', exist_ok=True)
    os.makedirs('/app/output', exist_ok=True)
    os.makedirs('/app/thumbnails', exist_ok=True)
    os.makedirs('/app/database', exist_ok=True)
    
    # 啟動應用
    socketio.run(app, host='0.0.0.0', port=5005, debug=False, allow_unsafe_werkzeug=True)
