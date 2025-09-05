// Shared helpers
function showToast(message, type='info'){
  const t = document.getElementById('appToast') || (()=>{
    const el = document.createElement('div');
    el.id='appToast'; el.className='toast'; document.body.appendChild(el); return el;
  })();
  t.textContent = message;
  t.classList.add('show');
  setTimeout(()=> t.classList.remove('show'), 1800);
}

async function updateQueueStatus(){
  try{
    const res = await fetch('/queue?summary=1');
    const html = await res.text();
    const tmp = new DOMParser().parseFromString(html, 'text/html');
    
    // 更新排隊數量
    const processingCount = tmp.getElementById('processingCount')?.textContent || '0';
    const pendingCount = tmp.getElementById('pendingCount')?.textContent || '0';
    
    document.getElementById('processingCount')?.replaceChildren(document.createTextNode(processingCount));
    document.getElementById('queueCount')?.replaceChildren(document.createTextNode(pendingCount));
    
    // 更新連接狀態 - 如果能獲取到數據就表示服務正常
    document.getElementById('queueStatus')?.replaceChildren(document.createTextNode('系統連接正常，服務運行中'));
  }catch(e){
    console.error('更新排隊狀態失敗:', e);
    document.getElementById('queueStatus')?.replaceChildren(document.createTextNode('無法連線到系統服務'));
  }
}

// ===== index.html =====
function previewImage(file){
  const reader = new FileReader();
  reader.onload = (e)=>{
    const el = document.getElementById('imagePreview');
    el.innerHTML = `<div class="preview"><img src="${e.target.result}" alt="預覽"></div>`;
  };
  reader.readAsDataURL(file);
}
function updateStatus(title, message, progress, isError=false){
  document.getElementById('statusCard')?.classList.remove('hidden');
  document.getElementById('statusTitle')?.replaceChildren(document.createTextNode(title));
  document.getElementById('statusMessage')?.replaceChildren(document.createTextNode(message));
  const bar = document.getElementById('progressBar');
  if(bar){ bar.style.width = (progress||0) + '%'; }
  if(isError){ showToast(message, 'danger'); }
}
async function loadRecentTasks(){
  try{
    const res = await fetch('/history?limit=5');
    const html = await res.text();
    const doc = new DOMParser().parseFromString(html,'text/html');
    const tasks = [...doc.querySelectorAll('.task-item')].slice(0,5).map(el=>JSON.parse(el.dataset.task));
    const list = document.getElementById('recentTasks');
    if(!tasks.length){ list.innerHTML = '<div class="subtle" style="text-align:center">暫無任務</div>'; return; }
    list.innerHTML = tasks.map(t=>`
      <div class="item">
        <div class="thumb">${t.thumbnail_filename? `<img src="/thumbnail/${t.thumbnail_filename}"/>`:`<span class="subtle">無縮圖</span>`}</div>
        <div style="display:flex; flex-direction:column; justify-content:space-between; min-height:84px;">
          <div style="font-weight:700;">${(t.prompt||'').slice(0,40)}${(t.prompt||'').length>40?'...':''}</div>
          <div class="row small subtle" style="margin-top:auto;">
            <span class="tag">${t.width}×${t.height}</span>
            <span class="tag">${t.duration==81?'5秒':'8秒'}</span>
            <span class="tag">${t.status}</span>
          </div>
        </div>
        <div class="row">
          <a class="btn secondary" href="/task/${t.task_id}">查看</a>
        </div>
      </div>
    `).join('');
  }catch(e){ /* ignore */ }
}

// ===== history.html =====
function filterByStatus(status){
  const url = new URL(location.href);
  
  // 清除搜尋參數，因為狀態篩選應該是獨立的
  url.searchParams.delete('search');
  
  // 設定或清除狀態參數
  if(status) {
    url.searchParams.set('status', status);
  } else {
    url.searchParams.delete('status');
  }
  
  // 重置到第一頁
  url.searchParams.delete('page');
  
  location.href = url.toString();
}

async function refreshHistory(){
  try{
    // 重新載入當前頁面，保持所有參數
    location.reload();
    // 更新時間顯示
    document.getElementById('lastUpdate')?.replaceChildren(document.createTextNode(new Date().toLocaleString()));
    // showToast('已更新');
  }catch(e){ 
    showToast('更新失敗','danger'); 
  }
}

function jumpToPage(){
  const pageInput = document.getElementById('jumpPage');
  const page = parseInt(pageInput.value);
  const maxPage = parseInt(pageInput.max);
  
  if(isNaN(page) || page < 1 || page > maxPage){
    showToast(`請輸入 1 到 ${maxPage} 之間的頁碼`, 'danger');
    return;
  }
  
  const url = new URL(location.href);
  url.searchParams.set('page', page);
  location.href = url.toString();
}

// 支援 Enter 鍵跳轉
document.addEventListener('DOMContentLoaded', function() {
  const jumpPageInput = document.getElementById('jumpPage');
  if(jumpPageInput){
    jumpPageInput.addEventListener('keypress', function(e) {
      if(e.key === 'Enter'){
        jumpToPage();
      }
    });
  }
  formatAllDates();
});
function playVideo(filename, title){
  const modal = document.getElementById('customVideoModal');
  if (!modal) {
    console.error('Modal element not found');
    return;
  }
  
  // Set modal content
  document.getElementById('videoModalTitle').textContent = (title||'影片播放').slice(0,50);
  document.getElementById('videoPlayer').innerHTML = `
     <video controls autoplay>
       <source src="/video/${filename}" type="video/mp4">
       您的瀏覽器不支援影片播放。
     </video>`;
  document.getElementById('modalDownloadBtn').href = '/download/'+filename;
  
  // Show custom modal with proper class management
  modal.classList.remove('hidden');
  modal.style.display = 'flex';
  
  // Force reflow and add show class
  modal.offsetHeight;
  modal.classList.add('show');
  
  // Prevent body scroll
  document.body.style.overflow = 'hidden';
  
  console.log('Modal opened, classes:', modal.className);
}

function closeVideoModal(){
  const modal = document.getElementById('customVideoModal');
  if (!modal) return;
  
  // Remove show class first
  modal.classList.remove('show');
  
  // After transition, hide completely
  setTimeout(() => {
    modal.classList.add('hidden');
    modal.style.display = 'none';
    document.getElementById('videoPlayer').innerHTML = '';
  }, 300);
  
  // Restore body scroll
  document.body.style.overflow = '';
  
  console.log('Modal closed');
}

// Add keyboard and click-outside support for video modal
document.addEventListener('DOMContentLoaded', function() {
  // ESC key support
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      const modal = document.getElementById('customVideoModal');
      if (modal && !modal.classList.contains('hidden')) {
        closeVideoModal();
      }
    }
  });
  
  // Click outside to close
  document.addEventListener('click', function(e) {
    const modal = document.getElementById('customVideoModal');
    if (modal && !modal.classList.contains('hidden')) {
      if (e.target === modal) {
        closeVideoModal();
      }
    }
  });
});
async function deleteTask(taskId, taskTitle){
  if(!confirm(`確定要刪除任務「${taskTitle}」嗎？此操作將無法復原。`)) return;
  try{
    const btn = document.querySelector(`button[onclick*="${taskId}"]`);
    if(btn){ btn.disabled = true; btn.textContent = '刪除中...'; }
    const res = await fetch('/api/delete/'+taskId, { method:'DELETE' });
    const data = await res.json();
    if(data.success){ showToast('已刪除'); location.reload(); }
    else { throw new Error(data.error||'刪除失敗'); }
  }catch(e){ showToast(e.message,'danger'); }
}

// ===== detail.html =====
function copyPrompt(){
  const el = document.createElement('textarea');
  el.value = (window.__TASK_PROMPT__||''); document.body.appendChild(el);
  el.select(); try{ document.execCommand('copy'); showToast('已複製'); }catch(e){ fallbackCopyTextToClipboard(el.value); }
  document.body.removeChild(el);
}
function fallbackCopyTextToClipboard(text){
  navigator.clipboard?.writeText(text).then(()=>showToast('已複製'),()=>showToast('複製失敗','danger'));
}
function shareVideo(){
  const fn = (window.__TASK_OUTPUT__||'');
  if(!fn){ showToast('尚無影片'); return; }
  const url = location.origin + '/video/'+ fn;
  const dl = location.origin + '/download/'+ fn;
  const su = document.getElementById('shareUrl');
  const du = document.getElementById('downloadUrl');
  if(su) su.value = url; if(du) du.value = dl;
  const overlay = document.getElementById('shareOverlay');
  if(overlay){ overlay.classList.add('show'); document.body.style.overflow='hidden'; }
}
function closeShare(){
  const overlay = document.getElementById('shareOverlay');
  if(overlay){ overlay.classList.remove('show'); document.body.style.overflow=''; }
}
function toggleFullscreen(){
  const v = document.getElementById('mainVideo');
  const btn = document.querySelector('.video-fullscreen-btn i');
  
  if (!document.fullscreenElement) {
    // 進入全螢幕
    if(v.requestFullscreen) {
      v.requestFullscreen();
    } else if(v.webkitRequestFullscreen) {
      v.webkitRequestFullscreen();
    } else if(v.msRequestFullscreen) {
      v.msRequestFullscreen();
    } else if(v.mozRequestFullScreen) {
      v.mozRequestFullScreen();
    }
    
    // 更新按鈕圖示
    if(btn) {
      btn.className = 'fa-solid fa-compress';
    }
  } else {
    // 退出全螢幕
    if(document.exitFullscreen) {
      document.exitFullscreen();
    } else if(document.webkitExitFullscreen) {
      document.webkitExitFullscreen();
    } else if(document.msExitFullscreen) {
      document.msExitFullscreen();
    } else if(document.mozCancelFullScreen) {
      document.mozCancelFullScreen();
    }
    
    // 更新按鈕圖示
    if(btn) {
      btn.className = 'fa-solid fa-expand';
    }
  }
}

// 監聽全螢幕狀態變化
document.addEventListener('fullscreenchange', updateFullscreenButton);
document.addEventListener('webkitfullscreenchange', updateFullscreenButton);
document.addEventListener('mozfullscreenchange', updateFullscreenButton);
document.addEventListener('MSFullscreenChange', updateFullscreenButton);

function updateFullscreenButton() {
  const btn = document.querySelector('.video-fullscreen-btn i');
  if(btn) {
    if(document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement) {
      btn.className = 'fa-solid fa-compress';
    } else {
      btn.className = 'fa-solid fa-expand';
    }
  }
}

// ===== queue.html =====
async function refreshStatus(){
  try{
    const res = await fetch(location.href);
    const html = await res.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const container = document.getElementById('queueRoot');
    const newRoot = doc.getElementById('queueRoot');
    if(container && newRoot) {
      container.innerHTML = newRoot.innerHTML;
      // 確保時間顯示使用一致的本地格式
      document.getElementById('lastUpdate')?.replaceChildren(document.createTextNode(new Date().toLocaleString()));
      // 重新格式化新插入的時間
      if(typeof formatAllDates === 'function'){
        formatAllDates();
      }
    }
    // showToast('已更新');
  }catch(e){ showToast('更新失敗','danger'); }
}
function updateQueueDisplay(data){
  // placeholder for compatibility with websocket push
}

// ===== unified datetime formatting =====
function formatAllDates(){
  const formatter = new Intl.DateTimeFormat(undefined, { year:'numeric', month:'numeric', day:'numeric', hour:'numeric', minute:'2-digit', second:'2-digit', hour12:false });
  document.querySelectorAll('.dt[data-dt]').forEach(el=>{
    const raw = el.getAttribute('data-dt');
    if(!raw || raw==='-' ){ el.textContent = '-'; return; }
    let d;
    try { d = new Date(raw.includes('Z')|| /[+-]\d\d:?\d\d$/.test(raw) ? raw : raw + 'Z'); } catch(e){ d = null; }
    if(d && !isNaN(d.getTime())){
      el.textContent = formatter.format(d);
    } else {
      el.textContent = raw;
    }
  });
}
document.addEventListener('readystatechange',()=>{ if(document.readyState==='complete') formatAllDates(); });
window.formatAllDates = formatAllDates;
