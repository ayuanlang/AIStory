# 前后端任务池通信协议详解

## 一、通信拓扑结构

```
前端浏览器                   后端API服务器                    任务队列系统
┌─────────────┐           ┌──────────────┐              ┌──────────────┐
│  React App  │           │  FastAPI     │              │  生成队列    │
│             │           │              │              │              │
│ 1.POST请求  │──────────→│ /generate/   │──────────→   │ enqueue      │
│   提交任务  │           │ image/video  │              │ task_queue   │
│             │           │              │              │              │
│ 2.轮询查询  │──────────→│ /generate/   │──────────→   │ 查询状态    │
│ (1-2秒)     │           │ jobs/{id}    │              │ from DB      │
│             │           │              │              │              │
│ 3.接收结果  │←──────────│ status,result│←──────────   │ 返回结果    │
│             │           │              │              │              │
└─────────────┘           └──────────────┘              └──────────────┘
                                 ↓
                          提供商API服务
                         (OpenAI/Sora等)
```

## 二、请求/响应流程（完整时间线）

### Phase 1: 前端提交任务

#### 请求1：POST /generate/image
```javascript
// 前端代码（api.js）
const response = await api.post('/generate/image', {
    prompt: "a beautiful landscape",
    negative_prompt: "",
    width: 1024,
    height: 768,
    aspect_ratio: "4:3",
    provider: "openai",  // 可选
    model: "dall-e-3",   // 可选
});

// 返回格式
{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",  // UUID
    "status": "queued",  // 立即返回状态
    "created_at": "2024-04-20T10:00:00Z"
}
```

#### 后端处理：POST /generate/image
```python
# endpoints.py L.22357
@router.post("/generate/image")
async def generate_image_endpoint(
    req: GenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 分两种模式：
    
    # 模式A：同步等待（10秒超时）
    try:
        result = await asyncio.wait_for(
            _run_generate_image(req, current_user, db),
            timeout=10  # IMAGE_SYNC_TIMEOUT_SECONDS
        )
        return {
            "url": result["url"],
            "metadata": result.get("metadata")
        }
    except asyncio.TimeoutError:
        # 超时则转为异步模式（见Phase 2）
        raise HTTPException(
            status_code=504,
            detail=f"Use /generate/image/submit for async polling"
        )
```

### Phase 2: 异步提交（推荐）

#### 请求2：POST /generate/image/submit
```javascript
// 前端代码（如果同步模式超时，前端自动转异步）
const response = await api.post('/generate/image/submit', {
    prompt: "a beautiful landscape",
    ...
});

// 返回：
{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "queued",
    "created_at": "2024-04-20T10:00:00Z"
}
```

#### 后端处理：POST /generate/image/submit
```python
# endpoints.py L.23788
@router.post("/generate/image/submit")
async def submit_image_generation(req: GenerationRequest, ...):
    job_id = str(uuid.uuid4())
    
    # 立即入队，不等待结果
    from app.services.generation_task_queue import enqueue_generation_task
    enqueue_generation_task(
        job_id=job_id,
        kind="image",
        user_id=user_id,
        payload={
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt,
            ...
        }
    )
    
    # 同步返回job_id
    return {
        "job_id": job_id,
        "status": "queued",
        "created_at": now_bj_iso()
    }
```

**数据库状态变化**：
```sql
-- generation_task_queue表
INSERT INTO generation_task_queue (
    job_id, kind, user_id, payload_json, status, created_at
) VALUES (
    '550e8400...', 'image', 123, '{"prompt":"..."}', 'queued', 1713607200.0
);

-- generation_job_state表
INSERT INTO generation_job_state (
    kind, job_id, user_id, status, payload_json, updated_at
) VALUES (
    'image', '550e8400...', 123, 'queued', '{...}', 1713607200.0
);
```

### Phase 3: 前端轮询查询状态

#### 请求3：GET /generate/image/jobs/{job_id}（循环）

```javascript
// 前端代码（React组件中）
const [jobStatus, setJobStatus] = useState('queued');
const [result, setResult] = useState(null);

useEffect(() => {
    const pollInterval = setInterval(async () => {
        try {
            // 1. 发起查询（带去缓存头）
            const response = await api.get(
                `/generate/image/jobs/${jobId}`,
                {
                    headers: {
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache'
                    }
                }
            );
            
            setJobStatus(response.data.status);
            
            // 2. 判断任务是否完成
            if (response.data.status === 'succeeded') {
                setResult(response.data.result.url);
                clearInterval(pollInterval);  // 停止轮询
            } else if (response.data.status === 'failed') {
                alert(response.data.error);
                clearInterval(pollInterval);
            }
        } catch (err) {
            console.error('Poll failed:', err);
        }
    }, 1000);  // 每1秒轮询一次
    
    return () => clearInterval(pollInterval);
}, [jobId]);

return (
    <div>
        <p>Status: {jobStatus}</p>
        {result && <img src={result} />}
    </div>
);
```

#### 后端处理：GET /generate/image/jobs/{job_id}
```python
# endpoints.py L.23937
@router.get("/generate/image/jobs/{job_id}")
def get_generate_image_job_status(job_id: str, ...):
    # 1. 先查内存缓存
    with IMAGE_JOB_LOCK:
        job = dict(IMAGE_JOB_STORE.get(job_id) or {})
    
    # 2. 若缓存miss且状态为queued/running，则从文件恢复
    if not job or status in {"queued", "running"}:
        file_job = _read_image_job_file(job_id)
        if file_job:
            with IMAGE_JOB_LOCK:
                IMAGE_JOB_STORE[job_id] = dict(file_job)
            job = dict(file_job)
    
    # 3. 返回当前状态
    return {
        "job_id": job_id,
        "kind": "image",
        "status": job.get("status"),     # "queued" | "running" | "succeeded" | "failed"
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "error": job.get("error"),       # if failed
        "result": {
            "url": job.get("result", {}).get("url"),
            "metadata": {...}
        },
        "provider": job.get("provider"),
        "model": job.get("model"),
        "elapsed_seconds": (time.time() - job.get("started_at", 0))
    }
```

**响应示例**：
```json
{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "kind": "image",
    "status": "running",
    "created_at": "2024-04-20T10:00:00Z",
    "started_at": "2024-04-20T10:00:02Z",
    "finished_at": null,
    "error": null,
    "result": null,
    "provider": "openai",
    "model": "dall-e-3",
    "elapsed_seconds": 5
}

// 任务完成后：
{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "kind": "image",
    "status": "succeeded",  // ← 状态变化！
    "created_at": "2024-04-20T10:00:00Z",
    "started_at": "2024-04-20T10:00:02Z",
    "finished_at": "2024-04-20T10:02:45Z",  // ← 新增
    "error": null,
    "result": {
        "url": "https://oss.example.com/uploads/123/image-uuid.png",
        "metadata": {...}
    },
    "provider": "openai",
    "model": "dall-e-3",
    "elapsed_seconds": 163
}
```

### Phase 4：提供商回调（可选，加速结果）

#### 请求4：POST /generate/callback/{ticket}（由提供商发起）

```
提供商API（OpenAI/Sora）
        │
        │ 任务完成后调用回调URL
        ↓
    后端HTTP服务器
        │
        → POST /generate/callback/image-job-550e8400...
        
参数体：
{
    "status": "succeeded",
    "image_url": "https://provider-cdn.com/image.png",
    "task_id": "task_abc123"
}
```

#### 后端处理：POST /generate/callback/{ticket}
```python
# endpoints.py L.26190
@router.post("/generate/callback/{ticket}")
async def receive_generation_callback(ticket: str, request: Request, ...):
    # 1. 解析回调凭证
    stable_ticket = str(ticket or "").strip()  # "image-job-550e8400..."
    
    # 2. 从数据库查找对应任务
    matches = find_generation_job_states_by_callback_ticket(
        kind="image",
        callback_ticket=stable_ticket
    )
    
    for job_data in matches:
        job_id = job_data.get("job_id")
        
        # 3. 更新任务状态为completed
        _set_image_job(
            job_id,
            status="succeeded",
            finished_at=now_bj_iso(),
            result={"url": image_url_from_callback}
        )
    
    return {"status": "ok"}
```

**优势**：
- 无需前端继续轮询，立即通知结果
- 减少网络请求
- 实时性最高

### Phase 5：前端接收结果

前端轮询时发现 `status == "succeeded"`，停止轮询并显示结果。

## 三、任务池管理的双层存储

### Layer 1：内存缓存（快速查询）
```python
# endpoints.py
IMAGE_JOB_STORE: Dict[str, Dict] = {}  # {job_id: job_data}
IMAGE_JOB_LOCK = threading.Lock()       # 线程安全

VIDEO_JOB_STORE: Dict[str, Dict] = {}
VIDEO_JOB_LOCK = threading.Lock()

# 特点：
# ✓ O(1)查询速度
# ✗ 进程重启丢失
# ✗ 多进程间不共享
```

### Layer 2：数据库持久化（可靠性）
```python
# generation_task_queue.py
generation_task_queue 表：
- 待执行任务队列（FIFO）
- status: queued/running/completed/failed/canceled
- 支持多进程共享

generation_job_state 表：
- 任务完整状态快照
- provider_callback_ticket: 提供商回调凭证
- 支持按callback_ticket查询
```

### Layer 3：文件持久化（超期恢复）
```python
# 若内存中的任务丢失，从文件恢复
_IMAGE_JOB_FILE_DIR = os.path.join(settings.UPLOAD_DIR, "_image_jobs")
_VIDEO_JOB_FILE_DIR = os.path.join(settings.UPLOAD_DIR, "_video_jobs")

# 文件名：{job_id}.json
# 路径：/uploads/_image_jobs/550e8400-e29b-41d4-a716-446655440000.json
```

## 四、前端轮询策略（并发控制）

### 限流机制
```javascript
// api.js L.400-430

// 图片任务轮询限流
const IMAGE_STATUS_MAX_CONCURRENT = 4;  // 最多同时轮询4个
let imageStatusInFlight = 0;
const imageStatusWaitQueue = [];

const acquireImageStatusSlot = async () => {
    if (imageStatusInFlight < IMAGE_STATUS_MAX_CONCURRENT) {
        imageStatusInFlight += 1;
        return;
    }
    // 超限则等待
    await new Promise((resolve) => {
        imageStatusWaitQueue.push(resolve);
    });
    imageStatusInFlight += 1;
};

// 视频任务轮询限流
const VIDEO_STATUS_MAX_CONCURRENT = 2;  // 视频更耗资源，限流更严

// 去重缓存（单飞）
const imageStatusSingleFlight = new Map();  // 防止同一任务重复查询

const fetchImageJobStatusLimited = async (jobId) => {
    const singleFlightKey = jobId;
    const existing = imageStatusSingleFlight.get(singleFlightKey);
    
    // 若已有相同查询在途，直接返回该Promise
    if (existing) {
        return existing;
    }
    
    const pending = (async () => {
        await acquireImageStatusSlot();
        try {
            return await api.get(`/generate/image/jobs/${jobId}`);
        } finally {
            releaseImageStatusSlot();
        }
    })();
    
    imageStatusSingleFlight.set(singleFlightKey, pending);
    try {
        return await pending;
    } finally {
        imageStatusSingleFlight.delete(singleFlightKey);
    }
};
```

**效果**：
- 100个任务只需4个并发轮询
- 自动排队等待，无需手动控制
- 避免前端发起过多HTTP请求

## 五、任务池查询API

### GET /generate/jobs/pool
```javascript
// 前端：获取所有任务状态
const allJobs = await api.get('/generate/jobs/pool', {
    params: {
        kind: "image",           // "image" | "video" | "all"
        running_only: true,      // 仅查询进行中的任务
        limit: 50                // 最多返回50条
    }
});

// 返回：
{
    "items": [
        {
            "job_id": "550e8400-...",
            "kind": "image",
            "status": "running",
            "created_at": "...",
            "started_at": "...",
            "finished_at": null,
            "provider": "openai",
            "model": "dall-e-3",
            "elapsed_seconds": 15
        },
        ...
    ],
    "total": 120,
    "limit": 50
}
```

#### 后端处理：GET /generate/jobs/pool
```python
# endpoints.py L.26589
@router.get("/generate/jobs/pool")
def get_generation_job_pool(
    kind: str = "all",       # "all" | "image" | "video"
    running_only: bool = False,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. 读取内存中的所有任务
    with IMAGE_JOB_LOCK:
        for job_id, payload in IMAGE_JOB_STORE.items():
            # 过滤过期任务
            if is_stale(payload):
                continue
            items.append(payload)
    
    with VIDEO_JOB_LOCK:
        for job_id, payload in VIDEO_JOB_STORE.items():
            if is_stale(payload):
                continue
            items.append(payload)
    
    # 2. 应用过滤和排序
    if running_only:
        items = [i for i in items if i["status"] in {"queued", "running"}]
    
    if kind != "all":
        items = [i for i in items if i["kind"] == kind]
    
    # 3. 返回限制条数
    items = items[:limit]
    
    return {
        "items": items,
        "total": len(items),
        "limit": limit
    }
```

**用途**：
- 前端显示"任务队列"界面
- 管理员监控所有任务
- 批量取消任务

## 六、错误处理与重试

### 超时处理
```javascript
// 前端：任务超时（900秒）
const MAX_JOB_TIMEOUT = 900 * 1000;  // 15分钟
const startTime = Date.now();

while (Date.now() - startTime < MAX_JOB_TIMEOUT) {
    const status = await fetchImageJobStatusLimited(jobId);
    
    if (status.status === "succeeded") {
        return status.result.url;
    }
    
    if (status.status === "failed") {
        throw new Error(status.error);
    }
    
    await sleep(1000);  // 等待1秒再查询
}

// 超时后的处理
throw new Error("Image generation timed out after 15 minutes");
```

### 后端超时处理
```python
# endpoints.py L.23950-23960
# asyncio.wait_for超时处理

except asyncio.TimeoutError:
    # 检查是否已通过callback完成
    current_job = IMAGE_JOB_STORE.get(job_id)
    if current_job and current_job["status"] == "succeeded":
        # 虽然超时，但已通过callback完成
        return result
    
    # 真正超时
    billing_service.log_failed_transaction(...)
    _set_image_job(
        job_id,
        status="failed",
        error=f"Image job timed out after 900s"
    )
```

## 七、完整时间线示例

```
时间点    | 事件                                  | 前端状态      | 后端DB状态
----------|--------------------------------------|--------------|------------------
10:00:00  | 用户点击"生成图片"                   | Loading      | 
10:00:01  | POST /generate/image/submit          | Loading      | status=queued
10:00:02  | 前端开始轮询 GET /jobs/{id}         | Loading      | status=queued
10:00:03  | 工作线程领取任务                      | Loading      | status=running
10:00:03  | 提交给OpenAI API                     | Loading      | status=running
10:00:04  | 前端轮询...                          | Loading      | status=running
10:00:05  | 前端轮询...                          | Loading      | status=running
...       | ...                                   | Loading      | status=running
10:02:00  | OpenAI返回图片URL                    | Loading      | 
10:02:01  | POST /callback/image-job-xxx通知     | Loading      | 
10:02:02  | 后端处理回调，更新状态               | Loading      | status=succeeded
10:02:03  | 前端下次轮询获得结果                 | Display      | status=succeeded
10:02:04  | 显示图片                              | Display      | 
```

## 八、关键参数

| 参数 | 值 | 含义 |
|------|-----|------|
| IMAGE_SYNC_TIMEOUT_SECONDS | 10秒 | 同步模式最多等待10秒 |
| IMAGE_JOB_MAX_RUNNING_SECONDS | 900秒 | 单个任务最长15分钟 |
| DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS | 600秒 | 向提供商轮询最多10分钟 |
| VIDEO_JOB_TIMEOUT_MS_DEFAULT | 900000ms | 前端最多等待15分钟 |
| IMAGE_STATUS_MAX_CONCURRENT | 4 | 前端最多同时轮询4个图片任务 |
| VIDEO_STATUS_MAX_CONCURRENT | 2 | 前端最多同时轮询2个视频任务 |
| GENERATION_QUEUE_POLL_SECONDS | 1秒 | 后端工作线程轮询间隔 |

## 九、异步架构优化

### 改造前（阻塞）
```
8个工作线程分别处理8个任务
worker-1: 等待API响应 (900秒阻塞)
worker-2: 等待API响应 (900秒阻塞)
...
总并发数：仅8个
```

### 改造后（非阻塞）
```
1个asyncio事件循环 + 8个worker协程
worker-1: 提交 → await → 可处理其他任务
worker-2: 提交 → await → 可处理其他任务
...
总并发数：100+个
```

---

**总结**：前后端通过 REST API 配合轮询机制实现异步任务管理，支持提供商回调加速，双层存储保证可靠性，前端限流防止过度请求。
