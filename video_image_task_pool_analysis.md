# 视频与图片任务池管理机制完整分析

## 一、任务池管理机制

### 1.1 架构概览

系统使用**数据库驱动的分布式任务队列**（不是内存队列），由以下核心组件组成：

| 组件 | 位置 | 职责 |
|------|------|------|
| `generation_task_queue.py` | backend/app/services/ | 任务队列核心逻辑 |
| `generation_job_state` 表 | PostgreSQL | 任务状态持久化 |
| `generation_task_queue` 表 | PostgreSQL | 待执行队列 |
| `endpoints.py` | backend/app/api/ | 队列处理器和作业管理 |
| `media_service.py` | backend/app/services/ | 实际生成逻辑 |

### 1.2 核心数据模型

#### generation_task_queue 表（待执行队列）
```sql
CREATE TABLE generation_task_queue (
    job_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,              -- 'image', 'video', 'montage'
    user_id INTEGER NOT NULL,
    payload_json TEXT NOT NULL,      -- 完整请求参数
    status TEXT NOT NULL,            -- 'queued', 'running', 'completed', 'failed', 'canceled'
    attempt_count INTEGER DEFAULT 0, -- 重试次数
    worker_id TEXT NULL,             -- 执行线程ID (如'generation-queue-1')
    created_at REAL NOT NULL,        -- 入队时间戳
    started_at REAL NULL,            -- 执行开始时间
    finished_at REAL NULL,           -- 执行完成时间
    last_heartbeat REAL NULL,        -- 最后心跳时间（用于失效检测）
    error TEXT NULL
);
CREATE INDEX idx_generation_task_queue_status_created_at ON generation_task_queue(status, created_at);
```

#### generation_job_state 表（任务状态与回调）
```sql
CREATE TABLE generation_job_state (
    kind TEXT NOT NULL,                      -- 任务种类
    job_id TEXT NOT NULL,
    user_id INTEGER NULL,
    status TEXT NULL,                        -- 任务当前状态
    provider_callback_ticket TEXT NULL,      -- 来自提供商的唯一凭证
    payload_json TEXT NOT NULL,              -- 完整任务状态快照
    updated_at REAL NOT NULL,
    PRIMARY KEY (kind, job_id)
);
CREATE INDEX idx_generation_job_state_kind_callback_ticket ON generation_job_state(kind, provider_callback_ticket);
```

### 1.3 任务生命周期

```
1. 入队 (enqueue_generation_task)
   ↓
   status = 'queued'
   created_at = time.time()
   attempt_count = 0
   
2. 领取 (claimed by worker via _claim_next_task)
   ↓
   status = 'running'
   started_at = time.time()
   worker_id = 'generation-queue-N'
   last_heartbeat = time.time()
   attempt_count += 1
   
3. 执行 (processor call)
   ↓
   asyncio.run(_run_generate_image_job / _run_generate_video_job)
   
4. 完成 (_finish_task)
   ↓
   status = 'completed' | 'failed' | 'canceled'
   finished_at = time.time()
   error = error_message (if applicable)
```

## 二、超时管理机制

### 2.1 超时类型与时间点

#### 关键参数定义（backend/app/api/endpoints.py）
```python
IMAGE_JOB_MAX_RUNNING_SECONDS = max(120, int(os.getenv("IMAGE_JOB_MAX_RUNNING_SECONDS", "900")))
VIDEO_JOB_MAX_RUNNING_SECONDS = max(120, int(os.getenv("VIDEO_JOB_MAX_RUNNING_SECONDS", "900")))
# 默认值：900秒 (15分钟)，最小值：120秒 (2分钟)
```

#### 关键参数定义（backend/app/services/media_service.py）
```python
DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS = int(os.getenv("VIDEO_POLL_TIMEOUT_SECONDS", "600"))
# 轮询超时：600秒 (10分钟)

DEFAULT_N1N_IMAGE_READ_TIMEOUT_SECONDS = max(120, int(os.getenv("N1N_IMAGE_READ_TIMEOUT_SECONDS", "300")))
# 图片读取超时：300秒 (5分钟)，最小120秒
```

### 2.2 超时时点的三层机制

#### 第一层：任务执行整体超时（最外层）
**从 `started_at` 开始计时，不是从 `created_at`**

```python
# endpoints.py _run_generate_image_job()
_set_image_job(job_id, status="running", started_at=now_bj_iso())

result = await asyncio.wait_for(
    _run_generate_image(
        req_obj,
        user_principal,
        db,
        job_progress_callback=_on_provider_task_id,
        provider_callback_ticket=provider_callback_ticket,
        provider_callback_url=provider_callback_url,
    ),
    timeout=IMAGE_JOB_MAX_RUNNING_SECONDS,  # 900秒
)
```

**超时处理**：
```python
except asyncio.TimeoutError:
    with IMAGE_JOB_LOCK:
        current_job = dict(IMAGE_JOB_STORE.get(job_id) or {})
    
    # 关键：若已通过callback完成，则忽略超时
    current_status = _normalize_generation_status(current_job.get("status"))
    current_result_url = _extract_job_result_url(current_job.get("result"))
    if current_status == "succeeded" and current_result_url:
        logger.info("[ImageJob] timeout ignored after callback finalization | job_id=%s", job_id)
        return  # ← 不报错，使用已完成的结果
    
    # 否则失败
    billing_service.log_failed_transaction(...)
    _set_image_job(job_id, status="failed", 
                   error=f"image job timed out after {IMAGE_JOB_MAX_RUNNING_SECONDS}s")
```

#### 第二层：队列失效检测与自动恢复
**如果running任务超过900秒无心跳，自动分配给其他worker**

```python
# generation_task_queue.py
_QUEUE_RECLAIM_SECONDS = max(900.0, float(os.getenv("GENERATION_QUEUE_RECLAIM_SECONDS", "900")))

def _claim_next_task(worker_id: str) -> Optional[Dict[str, Any]]:
    cutoff = time.time() - _QUEUE_RECLAIM_SECONDS  # 当前时间 - 900秒
    
    row = db.execute("""
        SELECT ... FROM generation_task_queue
        WHERE status = 'queued'
           OR (status = 'running' AND COALESCE(last_heartbeat, 0) < :cutoff)
        ORDER BY created_at ASC
        LIMIT 1
    """, {"cutoff": cutoff})
```

**含义**：
- 如果任务在 `last_heartbeat` 时间后的900秒内没有更新
- 则视为worker已崩溃，自动分配给其他worker重新执行
- `attempt_count` 会递增，允许失效任务多次重试

#### 第三层：向提供商轮询的超时
**默认600秒轮询，间隔2秒，最多轮询300次**

```python
# media_service.py _submit_and_poll_image_task()
async def _submit_and_poll_image_task(
    self, url, payload, api_key, log_tag, 
    extra_metadata=None, 
    poll_timeout_seconds: int = DEFAULT_VIDEO_POLL_TIMEOUT_SECONDS,  # 600秒
    poll_interval_seconds: int = 2
):
    # 1. 提交任务到提供商API
    resp = await asyncio.to_thread(_post, True)
    task_id = resp.json().get("id") or resp.json().get("task_id")
    
    # 2. 轮询结果
    max_attempts = max(1, int(poll_timeout_seconds / max(1, poll_interval_seconds)))
    # max_attempts = 600 / 2 = 300次
    
    for _ in range(max_attempts):
        await asyncio.sleep(poll_interval_seconds)  # 等待2秒
        try:
            p_resp = await asyncio.to_thread(_poll, True, task_id)
        except requests.exceptions.Timeout:
            continue  # 轮询超时则重试
        
        p_data = p_resp.json()
        status = str(p_data.get("status") or "").strip().lower()
        
        if status in ["succeeded", "success", "completed", "done"]:
            image_url = self._extract_any_image_output(p_data)
            return {"url": image_url, "metadata": {...}}
        
        if status in ["failed", "error", "canceled"]:
            return {"error": "Generation Failed", "details": p_data}
    
    # 300次轮询后仍未完成，返回超时
    return {"error": f"Timeout after {poll_timeout_seconds}s"}
```

### 2.3 超时机制的设计意图

| 机制 | 时间 | 目的 |
|------|------|------|
| 第一层（asyncio.wait_for） | 900秒 | 整个生成任务的绝对期限 |
| 第二层（失效检测） | 900秒 | 检测worker崩溃，自动转移任务 |
| 第三层（轮询） | 600秒 | 向提供商查询结果，不会超过第一层 |

**巧妙之处**：
- 900秒整体超时 > 600秒轮询超时
- 若轮询未得到结果，返回error由asyncio处理
- 若轮询成功但接近900秒，仍可通过callback机制获胜（见下文）

## 三、前后端协同机制

### 3.1 双通道等待结果

系统不仅轮询查询，还支持**提供商主动回调**，形成两种结果获取路径：

```
路径1（主动轮询）：
后端 → GET /provider_api/{task_id} → 获取status → 若完成则获取URL

路径2（被动回调）：
提供商完成任务后 → POST /generate/callback/{ticket} 
                → 更新 generation_job_state 
                → 后续轮询发现已完成
```

### 3.2 提供商回调机制详解

#### 回调凭证生成
```python
# endpoints.py _run_generate_image_job()

# 为每个任务生成唯一回调凭证
provider_callback_ticket = f"image-job-{job_id}"  # 例：'image-job-550e8400-e29b-41d4-a716-446655440000'

# 生成回调URL（提供商将POST到此URL）
provider_callback_url = str(media_service._resolve_provider_callback_url(
    {}, 
    provider_callback_ticket
) or "").strip()

# 传给执行函数
await _run_generate_image(
    req_obj,
    user_principal,
    db,
    provider_callback_ticket=provider_callback_ticket,
    provider_callback_url=provider_callback_url,
)
```

#### 回调接收处理
```python
# endpoints.py
@router.post("/generate/callback/{ticket}")
async def receive_generation_callback(ticket: str, request: Request, response: Response):
    stable_ticket = str(ticket or "").strip()
    
    # 1. 接收提供商的POST请求
    payload = await request.json()
    
    # 2. 查询对应的任务
    matches = find_generation_job_states_by_callback_ticket(
        kind="image",
        callback_ticket=stable_ticket
    )
    
    # 3. 更新任务状态为 'succeeded'，保存结果URL
    # 此后的轮询将发现任务已完成，不再轮询
```

#### 超时与回调的配合
```python
# 关键：即使轮询超时，若callback已完成，则忽略超时
except asyncio.TimeoutError:
    current_job = dict(IMAGE_JOB_STORE.get(job_id) or {})
    
    # 检查callback是否已完成此任务
    if _normalize_generation_status(current_job.get("status")) == "succeeded":
        logger.info("[ImageJob] timeout ignored after callback finalization")
        return  # 使用callback的结果
    
    # 否则才真正失败
    _set_image_job(job_id, status="failed", error="timeout after 900s")
```

### 3.3 前端交互API

#### 创建任务
```python
@router.post("/image/generate")  # 或 /video/generate
async def generate_image_endpoint(...):
    job_id = str(uuid.uuid4())
    
    # 入队任务
    enqueue_generation_task(
        job_id=job_id,
        kind="image",
        user_id=user_id,
        payload={
            "prompt": prompt,
            "provider": provider,
            "width": width,
            "height": height,
            ...
        }
    )
    
    return {
        "job_id": job_id,
        "status": "queued"
    }
```

#### 查询任务状态
```python
@router.get("/generate/task/{job_id}")
def get_generation_task_status(job_id: str):
    task = get_generation_task_status(job_id)
    return {
        "job_id": task["job_id"],
        "kind": task["kind"],
        "status": task["status"],  # 'queued', 'running', 'completed', 'failed'
        "created_at": task["created_at"],
        "started_at": task["started_at"],
        "finished_at": task["finished_at"],
        "error": task["error"],
        "attempt_count": task["attempt_count"]
    }
```

#### 取消任务
```python
@router.post("/generate/task/{job_id}/cancel")
def cancel_generation_task(job_id: str):
    # 仅能取消 'queued' 和 'running' 状态
    cancel_generation_task(job_id, reason="Task canceled by user")
```

### 3.4 前端轮询策略（建议）
```javascript
// 前端代码逻辑
const jobId = response.data.job_id;
let isComplete = false;

const pollInterval = setInterval(async () => {
    const status = await fetch(`/generate/task/${jobId}`).then(r => r.json());
    
    switch(status.status) {
        case 'queued':
            console.log('任务等待中');
            break;
        case 'running':
            console.log('任务执行中');
            break;
        case 'completed':
            console.log('任务完成！');
            isComplete = true;
            break;
        case 'failed':
            console.log('任务失败:', status.error);
            isComplete = true;
            break;
        case 'canceled':
            console.log('任务被取消');
            isComplete = true;
            break;
    }
    
    if (isComplete) {
        clearInterval(pollInterval);
    }
}, 1000);  // 1秒轮询一次
```

## 四、并行执行逻辑

### 4.1 工作线程池模型

#### 线程数计算
```python
# generation_task_queue.py
_POOL_CAPACITY = max(1, int(DB_POOL_CAPACITY_EFFECTIVE or 0))
_DEFAULT_WORKER_THREADS = min(8, max(2, int(DB_POOL_SIZE_EFFECTIVE or 2)))
_REQUESTED_WORKER_THREADS = max(1, int(os.getenv("GENERATION_QUEUE_WORKER_THREADS", ...)))

# 关键限制：不超过数据库连接池的50%
_WORKER_THREAD_CAP = max(1, _POOL_CAPACITY // 2)
_QUEUE_WORKER_THREADS = max(1, min(_REQUESTED_WORKER_THREADS, _WORKER_THREAD_CAP))

if _REQUESTED_WORKER_THREADS > _QUEUE_WORKER_THREADS:
    logger.warning(
        "generation queue workers capped to avoid DB pool starvation | requested=%s capped=%s pool_capacity=%s",
        _REQUESTED_WORKER_THREADS,
        _QUEUE_WORKER_THREADS,
        _POOL_CAPACITY,
    )
```

**例子**：
- 若 `DB_POOL_SIZE=20`，则 `_POOL_CAPACITY=20`
- 若 `GENERATION_QUEUE_WORKER_THREADS=8`（默认）
- 则实际线程数 = `min(8, 20/2)` = `min(8, 10)` = **8个线程**

**为什么限制？**
- 保留至少50%的数据库连接用于API请求和认证流程
- 防止队列任务饿死API服务

### 4.2 工作线程执行模型

#### 启动阶段
```python
# generation_task_queue.py start_generation_task_worker()

def start_generation_task_worker(processor: Callable) -> None:
    global _QUEUE_STARTED
    
    if not _try_acquire_queue_leader_lock():
        logger.info("generation queue worker startup skipped; another process holds the lock")
        return  # 在多进程场景下，仅一个进程启动队列
    
    _ensure_queue_table_ready()
    
    # 启动N个工作线程
    for index in range(_QUEUE_WORKER_THREADS):
        worker_name = f"generation-queue-{index + 1}"
        thread = threading.Thread(
            target=_worker_loop,
            args=(worker_name, processor),
            daemon=True,
            name=worker_name,
        )
        thread.start()
    
    _QUEUE_STARTED = True
```

#### 执行循环
```python
# generation_task_queue.py _worker_loop()

def _worker_loop(worker_name: str, processor: Callable) -> None:
    logger.info("generation queue worker started | worker=%s poll=%ss reclaim=%ss", 
                worker_name, _QUEUE_POLL_SECONDS, _QUEUE_RECLAIM_SECONDS)
    
    while not _QUEUE_STOP_EVENT.is_set():
        task = None
        try:
            # 1. 声明式领取任务（原子操作）
            task = _claim_next_task(worker_name)
            if not task:
                _QUEUE_STOP_EVENT.wait(_QUEUE_POLL_SECONDS)  # 1秒轮询间隔
                continue
            
            # 2. 处理任务（可能耗时）
            processor(task["kind"], task["job_id"], task["user_id"], task["payload"])
            
            # 3. 标记完成
            finalized = _finish_task(task["job_id"], status="completed", only_if_running=True)
            
            if not finalized:
                logger.info("task state changed externally | job_id=%s", task["job_id"])
        
        except asyncio.CancelledError:
            if task:
                _finish_task(task["job_id"], status="canceled", error="Task canceled by user")
        
        except Exception as exc:
            logger.exception("generation queue task failed | job_id=%s", (task or {}).get("job_id"))
            if task:
                _finish_task(task["job_id"], status="failed", error=str(exc))
```

#### 任务领取的原子性
```python
def _claim_next_task(worker_id: str) -> Optional[Dict[str, Any]]:
    cutoff = time.time() - _QUEUE_RECLAIM_SECONDS
    
    # 第一步：读取下一个待执行任务（FIFO）
    row = db.execute("""
        SELECT job_id, kind, user_id, payload_json
        FROM generation_task_queue
        WHERE status = 'queued'
           OR (status = 'running' AND COALESCE(last_heartbeat, 0) < :cutoff)
        ORDER BY created_at ASC
        LIMIT 1
    """, {"cutoff": cutoff})
    
    if not row:
        return None
    
    # 第二步：立即更新为 'running'（防止其他worker领取同一任务）
    now = time.time()
    result = db.execute("""
        UPDATE generation_task_queue
        SET status = 'running',
            worker_id = :worker_id,
            started_at = COALESCE(started_at, :started_at),
            last_heartbeat = :heartbeat,
            finished_at = NULL,
            error = NULL,
            attempt_count = attempt_count + 1
        WHERE job_id = :job_id
          AND (status = 'queued' OR (status = 'running' AND COALESCE(last_heartbeat, 0) < :cutoff))
    """)
    
    db.commit()
    
    # 只有成功更新的才返回（其他worker可能同时读了同一行）
    if (result.rowcount or 0) < 1:
        return None
    
    return {
        "job_id": str(row["job_id"]),
        "kind": str(row["kind"]),
        "user_id": int(row["user_id"]),
        "payload": json.loads(row["payload_json"])
    }
```

### 4.3 并发控制关键点

#### FIFO顺序保证
```sql
ORDER BY created_at ASC  -- 先进先出
LIMIT 1                 -- 一次仅领取一个
```

#### 失败重试机制
```python
attempt_count INTEGER DEFAULT 0  -- 记录重试次数

# 如果任务失败但未超过重试限制，可重新入队
if attempt_count < max_retries:
    status = 'queued'  # 重新入队
else:
    status = 'failed'  # 最终失败
```

#### 防死锁机制
```python
# 如果worker崩溃，任务不会永久卡住
# 原因：last_heartbeat在900秒后会被重新分配

if status = 'running' AND last_heartbeat < (now - 900s):
    # 此任务自动转给其他worker
    status = 'running'
    worker_id = 'generation-queue-2'
    attempt_count = 2  # 第二次尝试
```

### 4.4 同一任务内的异步并行

#### 智能路由的并行尝试
```python
# media_service.py _generate_with_smart_routing()

# 基于策略，可能并行尝试多个提供商
result = await self._generate_with_smart_routing(
    category="Image",
    provider=provider,
    api_strategy=selected_strategy,  # 'fixed' 或 'smart_default'
    primary_retry_limit=3,           # 同一提供商重试次数
    fallback_candidate_limit=3,      # 备选提供商数
)
```

#### 可能的并行模式（推测）
```python
# 如果策略是 smart_default
# 可能同时向多个提供商发送请求，返回第一个成功者

async def _try_multiple_providers(candidates):
    tasks = [
        self._submit_and_poll_image_task(provider1, ...),
        self._submit_and_poll_image_task(provider2, ...),
        self._submit_and_poll_image_task(provider3, ...),
    ]
    
    # 返回第一个成功的
    return await asyncio.wait(
        tasks, 
        return_when=asyncio.FIRST_COMPLETED
    )
```

## 五、数据库压力管理

### 5.1 连接池压力

#### 问题
- 队列工作线程都需要数据库连接
- 但API处理也需要连接
- 如果队列占用过多，API请求会饿死

#### 解决方案
```python
_WORKER_THREAD_CAP = max(1, _POOL_CAPACITY // 2)

# 例：DB连接池=20
# 队列工作线程 ≤ 10
# 保留 ≥ 10个连接用于API
```

### 5.2 任务清理策略

```python
def _cleanup_old_tasks() -> None:
    global _QUEUE_LAST_CLEANUP_TIME
    now = time.time()
    if now - _QUEUE_LAST_CLEANUP_TIME < 3600.0:
        return  # 每小时最多一次
    
    cutoff = now - 86400.0  # 删除1天前的任务
    
    db.execute("""
        DELETE FROM generation_task_queue 
        WHERE status IN ('completed', 'failed', 'canceled') 
        AND created_at < :cutoff
    """)
```

**何时触发**：
- 第一个工作线程检测（每次轮询）
- 时间间隔：每小时最多一次
- 删除对象：已完成/失败/取消的任务，超过1天

### 5.3 生成结果缓存清理

```python
_GENERATION_JOB_POOL_CACHE_TTL_SECONDS = 300  # 5分钟TTL
_GENERATION_JOB_POOL_CACHE_MAX_ITEMS = 1000   # 最多1000个

def _prune_generation_job_pool_cache_locked(now_ts: float) -> None:
    # 1. 删除过期条目（5分钟未访问）
    stale_keys = [
        key for key, payload in _GENERATION_JOB_POOL_CACHE.items()
        if (now_ts - float((payload or {}).get("ts") or 0.0)) > 300
    ]
    
    # 2. 如果超过1000个，删除最旧的
    if len(_GENERATION_JOB_POOL_CACHE) > 1000:
        ordered = sorted(
            _GENERATION_JOB_POOL_CACHE.items(),
            key=lambda item: float(((item[1] or {}).get("ts") or 0.0)),
        )
        overflow = len(_GENERATION_JOB_POOL_CACHE) - 1000
        for key, _ in ordered[:overflow]:
            _GENERATION_JOB_POOL_CACHE.pop(key, None)
```

## 六、完整时间轴示例

```
时间     | 事件                              | 表状态
---------|----------------------------------|---------------------------
09:00:00 | 用户点击"生成图片"               |
09:00:01 | POST /image/generate              |
09:00:02 | enqueue_generation_task()        | status='queued', created_at=09:00:02
         | 返回 job_id 给前端               |
09:00:02 | 前端轮询 /task/{job_id}          | status='queued'
09:00:03 | generation-queue-1 发现此任务    |
09:00:03 | _claim_next_task() 更新行         | status='running', started_at=09:00:03
         |                                   | worker_id='generation-queue-1'
         |                                   | last_heartbeat=09:00:03
09:00:03 | 调用 _run_generate_image_job()   |
09:00:03 | asyncio.wait_for(timeout=900秒)  |
09:00:04 | _submit_and_poll_image_task()    |
09:00:04 |  └─ POST /provider/image submit  |
09:00:05 |  └─ 获得 task_id='task_abc123'  |
09:00:07 |  └─ GET /provider/image/task_abc123  | 状态=processing
09:00:09 |  └─ GET /provider/image/task_abc123  | 状态=processing
...      | ...
09:05:03 | 提供商回调 POST /callback/image-job-xxx
         | 更新 generation_job_state        | status='succeeded', result_url=...
09:05:05 | 轮询 GET /provider/image/task_abc123 | 状态=succeeded, url=...
         | 立即返回结果                      |
09:05:05 | _set_image_job(status='completed')|
09:05:05 | _finish_task('completed')        | status='completed', finished_at=09:05:05
09:05:06 | 前端轮询，发现已完成              | 显示图片
```

## 七、关键文件与函数速查

| 功能 | 文件 | 函数/表 |
|------|------|---------|
| 入队 | generation_task_queue.py | `enqueue_generation_task()` |
| 领取 | generation_task_queue.py | `_claim_next_task()` |
| 执行 | endpoints.py | `_process_generation_queue_task()` |
| 图片任务 | endpoints.py | `_run_generate_image_job()` |
| 视频任务 | endpoints.py | `_run_generate_video_job()` |
| 轮询 | media_service.py | `_submit_and_poll_image_task()` |
| 回调 | endpoints.py | `receive_generation_callback()` |
| 完成 | generation_task_queue.py | `_finish_task()` |
| 查询 | generation_task_queue.py | `get_generation_task_status()` |
| 取消 | generation_task_queue.py | `cancel_generation_task()` |

## 八、性能优化建议

1. **减少轮询间隔**：若提供商API快速响应，可调低 `poll_interval_seconds` 从2秒到1秒
2. **增加轮询超时**：若任务通常耗时长，调高 `poll_timeout_seconds` 从600秒到1200秒
3. **增加工作线程**：若有多个DB连接池，增加 `GENERATION_QUEUE_WORKER_THREADS`
4. **启用异步智能路由**：使用 `smart_default` 策略并行尝试多个提供商
5. **优化数据库索引**：考虑添加 `(status, last_heartbeat)` 复合索引加快失效检测

---

**文档版本**：v1.0  
**最后更新**：2024年  
**相关代码位置**：
- [generation_task_queue.py](../../backend/app/services/generation_task_queue.py)
- [endpoints.py](../../backend/app/api/endpoints.py) (第599-661行, 第23543行, 第26022行)
- [media_service.py](../../backend/app/services/media_service.py) (第1943行, 第4255行, 第4376行)
