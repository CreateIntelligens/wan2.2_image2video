# ComfyUI 影片生成器

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

一個基於 Docker 的 ComfyUI 影片生成 API 系統，提供完整的網頁介面來生成和管理影片。

[功能特色](#功能特色) • [快速開始](#快速開始) • [使用教程](#使用教程) • [API文檔](#api文檔) • [故障排除](#故障排除)

</div>

## 🎬 功能特色

### 雙模式影片生成
- **單圖模式**：上傳一張圖片 + 提示詞生成影片
- **首尾幀模式**：上傳兩張圖片（首幀+尾幀）+ 提示詞生成影片

### 完整的 Web 界面
- 🎨 **響應式設計**：支援桌面和行動裝置
- 📤 **拖拽上傳**：直覺的圖片上傳體驗
- ⚡ **即時監控**：WebSocket 即時狀態更新
- 📊 **排隊管理**：多任務排隊和進度追蹤
- 📚 **歷史記錄**：完整的生成歷史和搜尋功能
- 🎥 **影片播放**：內建影片播放器和下載功能
- 🖼️ **縮圖預覽**：自動生成影片縮圖

### 技術特色
- 🐳 **Docker 容器化**：一鍵部署，環境隔離
- 🔄 **自動任務處理**：智能排隊和錯誤恢復
- 💾 **SQLite 數據庫**：輕量級數據存儲
- 🔌 **ComfyUI 整合**：無縫對接現有 ComfyUI 系統

## 🚀 快速開始

### 前置要求

- Docker 和 Docker Compose
- 運行中的 ComfyUI 服務（預設在 8188 埠）
- 至少 12GB 可用記憶體

### 一鍵部署

1. **克隆專案**
```bash
git clone <repository-url>
cd wan2_2_i2v
```

2. **配置環境**
```bash
# 編輯 .env 文件，設定 ComfyUI 路徑
echo "COMFYUI_PATH=/path/to/your/ComfyUI" > .env
```

3. **啟動服務**
```bash
docker-compose up -d
```

4. **訪問系統**
```
http://localhost:5005
```

就是這麼簡單！🎉

## 📖 使用教程

### 單圖模式

1. 在主頁選擇「單圖生成」模式
2. 輸入詳細的提示詞描述
3. 上傳一張圖片（支援 JPG/PNG/GIF）
4. 選擇影片尺寸：
   - `480 x 832`（直向）
   - `832 x 480`（橫向）
5. 選擇影片時長：
   - `5秒`（約4分鐘處理時間）
   - `8秒`（約7分鐘處理時間）
6. 點擊「開始生成影片」

### 首尾幀模式

1. 在主頁選擇「首尾幀生成」模式
2. 輸入詳細的提示詞描述
3. 分別上傳首幀和尾幀圖片
4. 選擇相同的尺寸和時長設定
5. 點擊「開始生成影片」

### 任務管理

- **即時監控**：在排隊狀態頁面查看處理進度
- **歷史記錄**：在歷史記錄頁面瀏覽所有任務
- **任務詳情**：點擊任務查看詳細資訊和下載影片
- **搜尋功能**：根據提示詞或檔案名搜尋歷史任務

## 🏗️ 技術架構

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │    │   Flask App     │    │    ComfyUI     │
│                 │◄──►│                 │◄──►│                 │
│  - 響應式界面    │    │  - API 服務     │    │  - 影片生成     │
│  - WebSocket    │    │  - 任務管理     │    │  - 工作流處理   │
│  - 檔案上傳     │    │  - 數據庫操作   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   SQLite DB     │
                       │                 │
                       │  - 任務記錄     │
                       │  - 狀態追蹤     │
                       │  - 歷史數據     │
                       └─────────────────┘
```

### 技術棧

- **後端**：Flask + Flask-SocketIO
- **前端**：原生 JavaScript + CSS
- **數據庫**：SQLite
- **容器化**：Docker + Docker Compose
- **圖像處理**：OpenCV + Pillow
- **ComfyUI 整合**：REST API

## 📁 專案結構

```
wan2_2_i2v/
├── docker-compose.yaml              # Docker 編排配置
├── .env                            # 環境變數配置
├── .gitignore                      # Git 忽略文件
├── README.md                       # 專案說明文件
├── wan2.2_i2v_14b_single.json     # 單圖工作流模板
├── wan2_2_i2v_14b_first_last.json # 首尾幀工作流模板
├── api/                            # 主應用目錄
│   ├── app.py                      # Flask 主應用
│   ├── database.py                 # 數據庫操作模組
│   ├── Dockerfile                  # 容器構建文件
│   ├── requirements.txt            # Python 依賴清單
│   ├── templates/                  # HTML 模板
│   │   ├── index.html             # 主頁面
│   │   ├── history.html           # 歷史記錄頁面
│   │   ├── detail.html            # 任務詳情頁面
│   │   └── queue.html             # 排隊狀態頁面
│   └── static/                     # 靜態資源
│       ├── css/app.css            # 主要樣式
│       ├── js/app.js              # JavaScript 功能
│       └── favicon.ico            # 網站圖標
├── input/                          # 用戶上傳圖片目錄
├── output/                         # 生成影片輸出目錄
├── thumbnails/                     # 影片縮圖目錄
└── database/                       # SQLite 數據庫文件目錄
```

## ⚙️ 配置說明

### 環境變數

在 `.env` 文件中配置以下變數：

```bash
# ComfyUI 安裝路徑
COMFYUI_PATH=/path/to/your/ComfyUI
```

### Docker Compose 配置

主要配置項目：

- **埠號對應**：`5005:5005`（可修改左側埠號）
- **ComfyUI 連接**：`host.docker.internal:8188`
- **資料持久化**：所有重要資料都掛載到本地目錄

### ComfyUI 工作流

系統使用兩個工作流模板：

1. **wan2.2_i2v_14b_single.json**：單圖模式
   - 節點 6：提示詞輸入
   - 節點 52：圖片輸入
   - 節點 75/76：尺寸設定
   - 節點 77：時長設定

2. **wan2_2_i2v_14b_first_last.json**：首尾幀模式
   - 節點 22：提示詞輸入
   - 節點 12：首幀圖片
   - 節點 28：尾幀圖片
   - 節點 33/34：尺寸設定
   - 節點 35：時長設定

## 🔌 API 文檔

### 主要端點

#### 生成影片
```http
POST /api/generate
Content-Type: multipart/form-data

Parameters:
- prompt: 提示詞 (required)
- mode: 生成模式 "single" | "first_last" (required)
- width: 影片寬度 (required)
- height: 影片高度 (required)
- duration: 影片時長 81|129 (required)
- image: 圖片文件 (single mode)
- first_image: 首幀圖片 (first_last mode)
- last_image: 尾幀圖片 (first_last mode)
```

#### 獲取任務狀態
```http
GET /api/task/{task_id}

Response:
{
  "task_id": "uuid",
  "status": "pending|processing|completed|failed",
  "prompt": "提示詞",
  "output_filename": "生成的影片檔名",
  "created_at": "建立時間",
  "completed_at": "完成時間"
}
```

#### 獲取排隊狀態
```http
GET /api/queue

Response:
{
  "local_queue": {
    "pending": 0,
    "processing": 1
  },
  "comfyui_queue": {
    "queue_running": [],
    "queue_pending": []
  }
}
```

### WebSocket 事件

- `task_completed`：任務完成通知
- `task_failed`：任務失敗通知
- `queue_update`：排隊狀態更新

## 🛠️ 故障排除

### 常見問題

#### 1. ComfyUI 連接失敗
**症狀**：頁面顯示「正在檢查系統連線...」
**解決方案**：
- 確認 ComfyUI 在 8188 埠正常運行
- 檢查防火牆設定
- 確認 Docker 網路配置

#### 2. 任務卡在處理中
**症狀**：任務長時間顯示「處理中」
**解決方案**：
```bash
# 使用恢復 API
curl -X POST http://localhost:5005/api/recover-stuck-tasks
```

#### 3. 影片生成失敗
**症狀**：任務狀態變為「失敗」
**解決方案**：
- 檢查 ComfyUI 日誌
- 確認工作流模板正確
- 檢查圖片格式和大小

#### 4. 容器啟動失敗
**症狀**：`docker-compose up` 失敗
**解決方案**：
```bash
# 檢查日誌
docker-compose logs

# 重新構建
docker-compose build --no-cache
docker-compose up -d
```

### 日誌查看

```bash
# 查看應用日誌
docker-compose logs -f comfyui-api

# 查看特定時間的日誌
docker-compose logs --since="1h" comfyui-api
```

### 性能優化

1. **記憶體使用**：建議至少 12GB 可用記憶體
2. **磁碟空間**：定期清理舊的影片文件
3. **並發處理**：系統設計為單任務處理，避免資源競爭

## 🔄 更新日誌

### v1.0.0
- ✨ 新增雙模式影片生成（單圖 + 首尾幀）
- 🎨 完整的響應式 Web 界面
- 📊 任務排隊和狀態管理
- 🔄 WebSocket 即時通知
- 📚 歷史記錄和搜尋功能
- 🐳 Docker 容器化部署
- 🖼️ 自動縮圖生成
- 🔌 ComfyUI API 整合

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

## 📄 授權

本專案採用 MIT 授權條款。

---

<div align="center">
Made with ❤️ by Create Intelligens Inc.
</div>
