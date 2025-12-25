import os
import json
import asyncio
import time

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse, FileResponse, JSONResponse
import httpx

#  Bot API Server监听端口
UPSTREAM = f"http://127.0.0.1:{os.environ.get('TELEGRAM_UPSTREAM_PORT', '8081')}"
app = Starlette(debug=False)

WORK_DIR = os.environ.get("TELEGRAM_WORK_DIR", "/tmp/telegram-bot-api-data")
DOWNLOAD_WAIT_SECONDS = float(os.environ.get("TELEGRAM_DOWNLOAD_WAIT_SECONDS", "8"))
DOWNLOAD_POLL_INTERVAL_MS = int(os.environ.get("TELEGRAM_DOWNLOAD_POLL_INTERVAL_MS", "200"))

_INFLIGHT_LOCKS: dict[str, asyncio.Lock] = {}
_INFLIGHT_LAST_SEEN: dict[str, float] = {}

def _inflight_key(token_enc: str | None, file_id: str | None) -> str:
    return f"{token_enc or ''}:{file_id or ''}"

def _get_inflight_lock(key: str) -> asyncio.Lock:
    lock = _INFLIGHT_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _INFLIGHT_LOCKS[key] = lock
    _INFLIGHT_LAST_SEEN[key] = time.time()
    return lock

def _cleanup_inflight_locks(max_entries: int = 1024, ttl_seconds: float = 300.0) -> None:
    if len(_INFLIGHT_LOCKS) <= max_entries:
        return
    now = time.time()
    for key, lock in list(_INFLIGHT_LOCKS.items()):
        last = _INFLIGHT_LAST_SEEN.get(key, 0.0)
        if (now - last) > ttl_seconds and (not lock.locked()):
            _INFLIGHT_LOCKS.pop(key, None)
            _INFLIGHT_LAST_SEEN.pop(key, None)

def _normalize_proxy_prefix(raw: str | None) -> str:
    s = str(raw or "").strip()
    if not s or s == "/":
        return ""
    if not s.startswith("/"):
        s = "/" + s
    return s.rstrip("/")

def _normalize_bot_api_file_path(raw_fp: str | None, token_enc: str | None) -> str:
    if not raw_fp:
        return ""

    fp = str(raw_fp).replace("\\", "/").lstrip("/")

    if token_enc:
        marker = f"/{token_enc}/"
        idx = fp.find(marker)
        if idx >= 0:
            fp = fp[idx + len(marker) :]
        elif fp.startswith(f"{token_enc}/"):
            fp = fp[len(token_enc) + 1 :]

    parts = [p for p in fp.split("/") if p]
    roots = {
        "documents",
        "photos",
        "videos",
        "video_notes",
        "voice",
        "audio",
        "animation",
        "animations",
        "stickers",
        "files",
        "thumbnails",
        "profile_photos",
    }
    for i, p in enumerate(parts):
        if p in roots:
            return "/".join(parts[i:])
    return fp

def _build_local_candidates(work_dir: str, token_enc: str | None, rel_path: str | None) -> list[str]:
    candidates = []
    rp = str(rel_path or "").strip().lstrip("/")
    if token_enc and rp:
        candidates.append(os.path.join(work_dir, token_enc, rp))
    if rp:
        candidates.append(os.path.join(work_dir, rp))
    return candidates

def _try_file_response(candidates: list[str]):
    for p in candidates:
        try:
            if p and os.path.isfile(p):
                return FileResponse(p)
        except Exception:
            pass
    return None

async def root(request: Request):
    return JSONResponse({"ok": True})

async def proxy(request: Request):
    path = request.path_params.get("path", "")
    # 兜底：如果下游请求把 file_path 带成了“工作目录前缀”，这里直接改写成相对路径再转发给 telegram-bot-api
    path_for_upstream = path.lstrip("/")
    if path_for_upstream.startswith("file/"):
        # 形如：file/bot<TOKEN>/<file_path>
        # 我们只需要把 <file_path> 规范化成 documents/... 这种相对路径
        rest = path_for_upstream[len("file/") :]
        if rest.startswith("bot"):
            token_enc = rest[3:].split("/", 1)[0] or None
            after_bot = rest.split("/", 1)[1] if "/" in rest else ""
            fixed = _normalize_bot_api_file_path(after_bot, token_enc)
            if fixed:
                path_for_upstream = f"file/bot{token_enc}/{fixed}"

    if path_for_upstream.startswith("file/"):
        rest = path_for_upstream[len("file/") :]
        token_enc = None
        rel = ""
        if rest.startswith("bot"):
            token_enc = rest[3:].split("/", 1)[0] or None
            rel = rest.split("/", 1)[1] if "/" in rest else ""
        rel_fixed = _normalize_bot_api_file_path(rel, token_enc)

        candidates = _build_local_candidates(WORK_DIR, token_enc, rel_fixed)
        resp = _try_file_response(candidates)
        if resp is not None:
            return resp

        # 如果本地没有这个文件（HF 不持久化），允许 CloudPaste 通过 query 传入 file_id 来触发回源下载：
        # query 上多带一个 file_id（例如 ?file_id=xxx）
        file_id = request.query_params.get("file_id") or request.query_params.get("fid")
        if token_enc and file_id:
            # 防抖：同一个 (token,file_id) 的回源下载只触发一次，避免并发 Range 请求重复打 getFile/重复等待落盘
            key = _inflight_key(token_enc, str(file_id))
            lock = _get_inflight_lock(key)
            try:
                async with lock:
                    resp_again = _try_file_response(_build_local_candidates(WORK_DIR, token_enc, rel_fixed))
                    if resp_again is not None:
                        return resp_again

                    async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
                        r = await client.get(f"{UPSTREAM}/bot{token_enc}/getFile", params={"file_id": file_id})
                        payload = None
                        try:
                            payload = r.json()
                        except Exception:
                            payload = None

                    if r.status_code == 200 and isinstance(payload, dict) and payload.get("ok") is True:
                        fp = None
                        try:
                            fp = (payload.get("result") or {}).get("file_path")
                        except Exception:
                            fp = None

                        rel2 = _normalize_bot_api_file_path(fp if isinstance(fp, str) else None, token_enc)
                        if rel2:
                            candidates2 = _build_local_candidates(WORK_DIR, token_enc, rel2)

                            waited = 0.0
                            interval = max(0.05, DOWNLOAD_POLL_INTERVAL_MS / 1000.0)
                            max_wait = max(0.0, DOWNLOAD_WAIT_SECONDS)
                            while waited <= max_wait:
                                resp2 = _try_file_response(candidates2)
                                if resp2 is not None:
                                    return resp2
                                if waited >= max_wait:
                                    break
                                await asyncio.sleep(interval)
                                waited += interval
            finally:
                _cleanup_inflight_locks()

    url = f"{UPSTREAM}/{path_for_upstream}"

    params = list(request.query_params.multi_items())

    headers = dict(request.headers)
    headers.pop("host", None)

    async def iter_request_body():
        async for chunk in request.stream():
            yield chunk


    is_file_download = path_for_upstream.startswith("file/")
    is_get_file = "/getFile" in ("/" + path_for_upstream)

    passthrough_allow = {
        "content-type",
        "content-disposition",
        "accept-ranges",
        "content-range",
        "etag",
        "cache-control",
        "last-modified",
    }

    client = httpx.AsyncClient(timeout=None, follow_redirects=True)
    if not is_file_download:
        try:
            r = await client.request(
                request.method,
                url,
                params=params,
                headers=headers,
                content=iter_request_body(),
            )
            resp_headers = {k: v for k, v in r.headers.items() if k.lower() in passthrough_allow}
            resp_headers.pop("content-length", None)
            resp_headers.pop("Content-Length", None)

            content_type = (r.headers.get("content-type") or "").lower()
            if is_get_file and r.status_code == 200 and "application/json" in content_type:
                try:
                    payload = r.json()
                    if isinstance(payload, dict) and payload.get("ok") is True and isinstance(payload.get("result"), dict):
                        result = payload.get("result") or {}
                        fp = result.get("file_path")
                        token_enc = None
                        p = path_for_upstream.lstrip("/")
                        if p.startswith("bot"):
                            token_enc = p[3:].split("/", 1)[0] or None

                        fixed = _normalize_bot_api_file_path(fp if isinstance(fp, str) else None, token_enc)
                        if fixed:
                            result["file_path"] = fixed
                            payload["result"] = result
                            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                            resp_headers.setdefault("content-type", "application/json")
                            resp_headers.pop("content-length", None)
                            resp_headers.pop("Content-Length", None)
                            return Response(content=body, status_code=r.status_code, headers=resp_headers)
                except Exception:
                    pass

            return Response(content=r.content, status_code=r.status_code, headers=resp_headers)
        finally:
            await client.aclose()

    req = client.build_request(
        request.method,
        url,
        params=params,
        headers=headers,
        content=iter_request_body(),
    )
    r = await client.send(req, stream=True)
    resp_headers = {k: v for k, v in r.headers.items() if k.lower() in passthrough_allow}

    async def iter_response():
        try:
            async for chunk in r.aiter_bytes():
                yield chunk
        finally:
            try:
                await r.aclose()
            finally:
                await client.aclose()

    return StreamingResponse(iter_response(), status_code=r.status_code, headers=resp_headers)

_PROXY_PREFIX = _normalize_proxy_prefix(os.environ.get("TELEGRAM_PROXY_PREFIX", "/tg"))
_PROXY_ROUTE = f"{_PROXY_PREFIX}/{{path:path}}" if _PROXY_PREFIX else "/{path:path}"
app.add_route("/", root, methods=["GET"])
app.add_route(
    _PROXY_ROUTE,
    proxy,
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
