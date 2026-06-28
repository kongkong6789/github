from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

AGENT_REACH_COMMAND = os.getenv("A2A_AGENT_REACH_BIN", "agent-reach")
MCPORTER_COMMAND = os.getenv("A2A_MCPORTER_BIN", "mcporter")
YT_DLP_COMMAND = os.getenv("A2A_YT_DLP_BIN", "yt-dlp")
JINA_READER_BASE_URL = os.getenv("A2A_JINA_READER_BASE_URL", "https://r.jina.ai/").rstrip("/") + "/"

LOGIN_REQUIRED_CHANNELS = {
    "bilibili",
    "rednote",
    "twitter",
    "x",
    "reddit",
}
PUBLIC_VIDEO_HOST_SUFFIXES = (
    "youtube.com",
    "youtu.be",
    "bilibili.com",
    "vimeo.com",
    "tiktok.com",
    "douyin.com",
)


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _safe_error(exc: BaseException) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    text = re.sub(r"(?i)(api[_-]?key|token|password|cookie|authorization)=\S+", r"\1=<redacted>", text)
    text = re.sub(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1<redacted>", text)
    return text[:500]


def _hostname_matches_suffix(hostname: str, suffixes: tuple[str, ...]) -> bool:
    return any(hostname == suffix or hostname.endswith(f".{suffix}") for suffix in suffixes)


def _dns_public_error(hostname: str) -> Optional[str]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except OSError:
        return "URL 域名无法解析，无法确认是否为公开地址。"
    addresses = {item[4][0] for item in infos if item[4]}
    if not addresses:
        return "URL 域名无法解析，无法确认是否为公开地址。"
    for raw_address in addresses:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError:
            return "URL 域名解析结果异常，无法确认是否为公开地址。"
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            return "URL 必须解析到公开互联网地址，不能指向 localhost 或内网 IP。"
    return None


def _public_url_or_error(
    url: str,
    *,
    resolve_dns: bool = False,
    allowed_host_suffixes: tuple[str, ...] = (),
) -> tuple[Optional[str], Optional[str]]:
    value = (url or "").strip()
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None, "URL 必须是公开 http/https 地址。"
    if parsed.username or parsed.password:
        return None, "URL 必须是公开 http/https URL，不能包含账号密码。"
    hostname = (parsed.hostname or "").strip().lower()
    if hostname in {"localhost", "0.0.0.0"} or hostname.endswith(".local"):
        return None, "URL 必须是公开 http/https 地址，不能指向 localhost 或内网 IP。"
    if allowed_host_suffixes and not _hostname_matches_suffix(hostname, allowed_host_suffixes):
        return None, "视频字幕读取只允许公开视频平台 URL。"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    ):
        return None, "URL 必须是公开 http/https 地址，不能指向 localhost 或内网 IP。"
    if resolve_dns:
        dns_error = _dns_public_error(hostname)
        if dns_error:
            return None, dns_error
    return urllib.parse.urlunparse(parsed), None


def _fetch_text(url: str, *, timeout_seconds: int, max_bytes: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "A2A-Ecommerce-Workbench/agent-reach-read-only",
            "Accept": "text/plain, text/markdown, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read(max_bytes + 1).decode("utf-8", errors="replace")


def _limit(value: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return min(max(parsed, minimum), maximum)


def _summarize_doctor(doctor: dict[str, Any]) -> dict[str, Any]:
    channels: list[dict[str, Any]] = []
    for name, raw in sorted(doctor.items()):
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or "warn").strip().lower()
        channels.append(
            {
                "name": name,
                "status": status if status in {"ok", "warn", "off", "error"} else "warn",
                "public_read": name not in LOGIN_REQUIRED_CHANNELS,
                "requires_login": name in LOGIN_REQUIRED_CHANNELS,
            }
        )
    return {
        "channel_count": len(channels),
        "available_count": sum(1 for item in channels if item["status"] == "ok"),
        "public_ready_count": sum(1 for item in channels if item["public_read"] and item["status"] == "ok"),
        "login_required_count": sum(1 for item in channels if item["requires_login"]),
        "channels": channels,
    }


def agent_reach_get_status() -> str:
    """只读检查 Agent-Reach CLI 和公开资料通道状态。"""
    try:
        completed = subprocess.run(
            [AGENT_REACH_COMMAND, "doctor", "--json"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except FileNotFoundError:
        return _json(
            {
                "status": "unavailable",
                "available": False,
                "read_only": True,
                "message": "未检测到 Agent-Reach CLI。",
                "next_actions": ["在终端手动安装 agent-reach 后运行 agent-reach doctor --json。"],
            }
        )
    except subprocess.TimeoutExpired:
        return _json(
            {
                "status": "error",
                "available": False,
                "read_only": True,
                "message": "Agent-Reach doctor 超时。",
            }
        )

    if completed.returncode != 0:
        return _json(
            {
                "status": "error",
                "available": False,
                "read_only": True,
                "message": "Agent-Reach doctor 执行失败。",
                "error": _safe_error(RuntimeError(completed.stderr or completed.stdout)),
            }
        )

    try:
        doctor = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        return _json(
            {
                "status": "error",
                "available": True,
                "read_only": True,
                "message": "Agent-Reach doctor 没有返回可解析的 JSON。",
                "error": _safe_error(exc),
            }
        )
    if not isinstance(doctor, dict):
        doctor = {}
    summary = _summarize_doctor(doctor)
    return _json(
        {
            "status": "ok",
            "available": True,
            "read_only": True,
            "permission_scope": "public_read_only",
            "summary": summary,
        }
    )


def agent_reach_read_public_web(url: str, max_chars: int = 6000, timeout_seconds: int = 20) -> str:
    """通过公开 Jina Reader URL 只读读取网页正文。"""
    public_url, error = _public_url_or_error(url, resolve_dns=True)
    if error:
        return _json({"status": "error", "read_only": True, "message": error})
    limit = _limit(max_chars, 1, 50000)
    timeout = _limit(timeout_seconds, 3, 60)
    assert public_url is not None
    reader_url = f"{JINA_READER_BASE_URL}{public_url}"
    read_cap = min(max(limit * 8, 4096), 1024 * 1024)
    try:
        content = _fetch_text(reader_url, timeout_seconds=timeout, max_bytes=read_cap)
    except (urllib.error.URLError, TimeoutError) as exc:
        return _json(
            {
                "status": "error",
                "read_only": True,
                "source_url": public_url,
                "reader_url": reader_url,
                "message": "公开网页读取失败。",
                "error": _safe_error(exc),
            }
        )
    truncated = len(content) > limit
    return _json(
        {
            "status": "ok",
            "read_only": True,
            "source_url": public_url,
            "reader_url": reader_url,
            "content": content[:limit],
            "char_count": len(content),
            "truncated": truncated,
        }
    )


def _quote_mcporter_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").strip() + "'"


def agent_reach_search_public_sources(query: str, limit: int = 5) -> str:
    """通过已配置的 MCPorter 搜索公开资料；不写入外部账号。"""
    normalized_query = (query or "").strip()
    if not normalized_query:
        return _json({"status": "error", "read_only": True, "message": "query 不能为空。"})
    safe_limit = _limit(limit, 1, 10)
    expression = f"exa.web_search_exa(query: {_quote_mcporter_string(normalized_query)}, numResults: {safe_limit})"
    try:
        completed = subprocess.run(
            [MCPORTER_COMMAND, "call", expression],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except FileNotFoundError:
        return _json(
            {
                "status": "unavailable",
                "available": False,
                "read_only": True,
                "message": "未检测到 mcporter，暂不能执行公开搜索。",
                "next_actions": ["安装并配置 Agent-Reach/MCPorter 后重试。"],
            }
        )
    except subprocess.TimeoutExpired:
        return _json({"status": "error", "read_only": True, "message": "公开搜索超时。"})
    if completed.returncode != 0:
        return _json(
            {
                "status": "error",
                "read_only": True,
                "message": "公开搜索执行失败。",
                "error": _safe_error(RuntimeError(completed.stderr or completed.stdout)),
            }
        )
    try:
        parsed = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        parsed = {"raw": completed.stdout}
    return _json(
        {
            "status": "ok",
            "read_only": True,
            "query": normalized_query,
            "limit": safe_limit,
            "results": parsed,
        }
    )


def _clean_vtt(text: str) -> str:
    lines = []
    seen: set[str] = set()
    for line in text.splitlines():
        value = line.strip()
        if not value or value == "WEBVTT" or "-->" in value or value.isdigit():
            continue
        value = re.sub(r"<[^>]+>", "", value)
        if value and value not in seen:
            seen.add(value)
            lines.append(value)
    return "\n".join(lines)


def agent_reach_read_video_transcript(
    url: str,
    language: str = "zh-Hans,en.*",
    max_chars: int = 12000,
    timeout_seconds: int = 60,
) -> str:
    """只读提取公开视频字幕；需要本机已安装 yt-dlp。"""
    public_url, error = _public_url_or_error(
        url,
        resolve_dns=True,
        allowed_host_suffixes=PUBLIC_VIDEO_HOST_SUFFIXES,
    )
    if error:
        return _json({"status": "error", "read_only": True, "message": error})
    assert public_url is not None
    limit = _limit(max_chars, 1, 100000)
    timeout = _limit(timeout_seconds, 10, 180)
    sub_langs = (language or "zh-Hans,en.*").strip()
    with tempfile.TemporaryDirectory(prefix="a2a-agent-reach-video-") as tempdir:
        try:
            completed = subprocess.run(
                [
                    YT_DLP_COMMAND,
                    "--skip-download",
                    "--write-auto-subs",
                    "--write-subs",
                    "--sub-langs",
                    sub_langs,
                    "--sub-format",
                    "vtt",
                    "--paths",
                    tempdir,
                    "--output",
                    "%(id)s.%(ext)s",
                    public_url,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            return _json(
                {
                    "status": "unavailable",
                    "available": False,
                    "read_only": True,
                    "message": "未检测到 yt-dlp，暂不能提取视频字幕。",
                    "next_actions": ["安装 yt-dlp 或通过 Agent-Reach 配置视频字幕通道后重试。"],
                }
            )
        except subprocess.TimeoutExpired:
            return _json({"status": "error", "read_only": True, "message": "视频字幕提取超时。"})
        if completed.returncode != 0:
            return _json(
                {
                    "status": "error",
                    "read_only": True,
                    "message": "视频字幕提取失败。",
                    "error": _safe_error(RuntimeError(completed.stderr or completed.stdout)),
                }
            )
        transcript_parts = []
        for path in sorted(Path(tempdir).glob("*.vtt")):
            transcript_parts.append(_clean_vtt(path.read_text(encoding="utf-8", errors="replace")))
        transcript = "\n".join(part for part in transcript_parts if part).strip()
        return _json(
            {
                "status": "ok" if transcript else "empty",
                "read_only": True,
                "source_url": public_url,
                "language": sub_langs,
                "content": transcript[:limit],
                "char_count": len(transcript),
                "truncated": len(transcript) > limit,
            }
        )


def agent_reach_read_logged_in_social(platform: str, query_or_url: str, requested_by: str = "") -> str:
    """登录态社媒读取只返回确认请求，不自动读取本机浏览器 Cookie。"""
    return _json(
        {
            "status": "confirmation_required",
            "read_only": True,
            "risk_level": "medium",
            "platform": (platform or "").strip(),
            "query_or_url": (query_or_url or "").strip(),
            "requested_by": (requested_by or "").strip(),
            "message": "需要人工确认使用专用账号或专用浏览器登录态；不会自动读取主浏览器 Cookie，也不会发帖、评论、点赞、私信或写入外部账号。",
            "next_actions": [
                "确认只读取公开可见内容。",
                "使用专用账号或独立 Cookie 边界。",
                "在权限与工具页记录确认后再由受控 MCP/CLI 通道执行。",
            ],
        }
    )
