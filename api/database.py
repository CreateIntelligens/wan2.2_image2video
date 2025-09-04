import sqlite3
import os
from datetime import datetime
import json

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化資料庫表格"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 建立任務歷史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    prompt TEXT NOT NULL,
                    image_filename TEXT NOT NULL,
                    second_image_filename TEXT,
                    generation_mode TEXT NOT NULL DEFAULT 'single',
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    duration INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    output_filename TEXT,
                    thumbnail_filename TEXT,
                    error_message TEXT,
                    comfyui_prompt_id TEXT
                )
            ''')
            
            # 添加新欄位（如果表已存在但缺少新欄位）
            try:
                cursor.execute('ALTER TABLE task_history ADD COLUMN second_image_filename TEXT')
            except sqlite3.OperationalError:
                pass  # 欄位已存在
            
            try:
                cursor.execute('ALTER TABLE task_history ADD COLUMN generation_mode TEXT NOT NULL DEFAULT "single"')
            except sqlite3.OperationalError:
                pass  # 欄位已存在
            
            # 建立索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_id ON task_history(task_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON task_history(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON task_history(created_at)')
            
            conn.commit()
    
    def add_task(self, task_id, prompt, image_filename, width, height, duration, generation_mode='single', second_image_filename=None):
        """新增任務到資料庫"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO task_history 
                (task_id, prompt, image_filename, second_image_filename, generation_mode, width, height, duration, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            ''', (task_id, prompt, image_filename, second_image_filename, generation_mode, width, height, duration))
            conn.commit()
            return cursor.lastrowid
    
    def update_task_status(self, task_id, status, **kwargs):
        """更新任務狀態"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 建立動態更新語句
            update_fields = ['status = ?']
            values = [status]
            
            if status == 'processing':
                update_fields.append('started_at = ?')
                values.append(datetime.now().isoformat())
            elif status == 'completed':
                update_fields.append('completed_at = ?')
                values.append(datetime.now().isoformat())
            
            for key, value in kwargs.items():
                if key in ['output_filename', 'thumbnail_filename', 'error_message', 'comfyui_prompt_id']:
                    update_fields.append(f'{key} = ?')
                    values.append(value)
            
            values.append(task_id)
            
            cursor.execute(f'''
                UPDATE task_history 
                SET {', '.join(update_fields)}
                WHERE task_id = ?
            ''', values)
            conn.commit()
    
    def get_task(self, task_id):
        """獲取單個任務資訊"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM task_history WHERE task_id = ?', (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_tasks(self, limit=50, offset=0, status=None):
        """獲取所有任務，支援分頁和狀態篩選"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM task_history'
            params = []
            
            if status:
                query += ' WHERE status = ?'
                params.append(status)
            
            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def search_tasks(self, search_term, limit=50, offset=0):
        """搜尋任務"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM task_history 
                WHERE prompt LIKE ? OR image_filename LIKE ?
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            ''', (f'%{search_term}%', f'%{search_term}%', limit, offset))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def count_tasks(self, status=None, search_term=None):
        """計算任務總數"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = 'SELECT COUNT(*) FROM task_history'
            params = []
            conditions = []
            
            if status:
                conditions.append('status = ?')
                params.append(status)
            
            if search_term:
                conditions.append('(prompt LIKE ? OR image_filename LIKE ?)')
                params.extend([f'%{search_term}%', f'%{search_term}%'])
            
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            
            cursor.execute(query, params)
            return cursor.fetchone()[0]
    
    def get_queue_status(self):
        """獲取排隊狀態統計"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    status,
                    COUNT(*) as count
                FROM task_history 
                WHERE status IN ('pending', 'processing')
                GROUP BY status
            ''')
            results = cursor.fetchall()
            
            status_counts = {'pending': 0, 'processing': 0}
            for status, count in results:
                status_counts[status] = count
                
            return status_counts
    
    def cleanup_old_tasks(self, days=30):
        """清理舊任務記錄"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM task_history 
                WHERE created_at < datetime('now', '-{} days')
                AND status IN ('completed', 'failed')
            '''.format(days))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
    
    def delete_task(self, task_id):
        """刪除任務記錄"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 先獲取任務資訊，用於刪除相關檔案
            cursor.execute('SELECT * FROM task_history WHERE task_id = ?', (task_id,))
            task = cursor.fetchone()
            
            if not task:
                return None
            
            # 刪除資料庫記錄
            cursor.execute('DELETE FROM task_history WHERE task_id = ?', (task_id,))
            conn.commit()
            
            return dict(task)
