"""DeepSeek 官方 API 客户端：发消息、拿 JSON、记用量（其余什么都不做）。

口径固定（2026-10-10 按官方文档核对，记录在 Manifest 里）：

- base_url `https://api.deepseek.com`（OpenAI 兼容），模型 `deepseek-flash`
  （官方说明：旧名 `deepseek-v4-flash` 仍被接受，但实际由 DeepSeek-V4.1-Flash 服务）；
- 思考模式**默认开启**，且官方说明开启时 `temperature` 不生效、部分工具调用选项受限。
  本实验依赖确定的单步输出，因此显式传 `thinking={"type": "disabled"}` 并 `temperature=0`；
- JSON 输出需要 `response_format={"type": "json_object"}`，且提示词里必须出现 "json"
  字样与示例（见 `prompts.py`）；官方明确提示 **JSON 模式偶发返回空内容**，
  因此空内容按"输出结构不合法"处理（`INVALID_SCHEMA / model_output`），不静默放行。

密钥只从环境变量读，不写进代码、不打印、不进日志。
"""

import json
import os
import ssl
import time
import urllib.error
import urllib.request

from ticketdesk import (
    config,  # noqa: F401 - 导入即加载项目 .env（项目约定：环境变量或 .env）
)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
API_KEY_ENV = "DEEPSEEK_API_KEY"


class ModelCallError(RuntimeError):
    """模型调用失败：带类别，便于运行记录区分故障来源。"""

    def __init__(self, kind, detail):
        super().__init__("%s: %s" % (kind, detail))
        self.kind = kind


def api_key():
    """读密钥；没有就明确失败（不落库、不打印）。

    按项目既有约定（见 `config.py`）密钥可以放在环境变量或项目 `.env` 里：
    `.env` 由 `config` 在导入时用 `load_dotenv` 加载，这里读的是同一个环境变量。
    """
    key = os.getenv(API_KEY_ENV)
    if not key:
        raise ModelCallError(
            "missing_key",
            "环境变量 %s 未设置：请在本机设置后重跑（密钥不进代码/Manifest/聊天）"
            % API_KEY_ENV,
        )
    return key


class DeepSeekClient:
    """最小客户端：一次 `chat/completions` 调用。"""

    def __init__(self, model=DEFAULT_MODEL, base_url=DEFAULT_BASE_URL,
                 timeout=120, opener=None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = opener or urllib.request.urlopen
        self.returned_models = []      # 每次响应里服务端回传的模型标识
        self.calls = 0

    def payload(self, messages, max_tokens=1024, thinking="disabled"):
        """请求体：思考模式、temperature、JSON 输出都写死在这里。"""
        return {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "thinking": {"type": thinking},
            "stream": False,
        }

    def complete(self, messages, max_tokens=1024):
        """发一次请求，返回 `{"content", "usage", "model", "latency_ms"}`。"""
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(self.payload(messages, max_tokens)).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + api_key(),
            },
            method="POST",
        )
        started = time.perf_counter()
        self.calls += 1
        try:
            with self._opener(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise ModelCallError("http_%d" % exc.code, detail) from exc
        except TimeoutError as exc:
            # 超时单独一类：运行记录按 MODEL_TIMEOUT / model 记，不混进 MODEL_FAILED
            raise ModelCallError("timeout", str(exc)) from exc
        except ssl.SSLError as exc:
            # TLS 握手/传输失败发生在模型请求这一侧，属于模型调用失败（修订 03），
            # 不能因为异常类型不是 URLError 就冒到运行器里记成 RUNNER_EXCEPTION
            raise ModelCallError("network", "SSL: " + str(exc)) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise ModelCallError("timeout", str(exc.reason)) from exc
            raise ModelCallError("network", str(exc)) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            message = json.loads(body)
            choice = message["choices"][0]["message"]
        except (ValueError, KeyError, IndexError) as exc:
            raise ModelCallError("bad_response", body[:400]) from exc
        content = choice.get("content") or ""
        if not content.strip():
            # 官方文档说明：开启 JSON 模式时可能偶发返回空内容
            raise ModelCallError("empty_content", "响应内容为空")
        returned = message.get("model")
        if returned:
            self.returned_models.append(returned)
        return {
            "content": content,
            "usage": message.get("usage") or {},
            "model": returned,
            "latency_ms": latency_ms,
        }


def usage_tokens(usage):
    """把 usage 折成总 token 数；拿不到就是 None（**不要记成 0**）。"""
    if not usage:
        return None
    total = usage.get("total_tokens")
    if isinstance(total, int):
        return total
    parts = [usage.get("prompt_tokens"), usage.get("completion_tokens")]
    known = [part for part in parts if isinstance(part, int)]
    return sum(known) if known else None


def parse_json_object(content):
    """把模型输出解析成 JSON 对象；不合法就抛错（不猜、不补）。"""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        raise ModelCallError("bad_json", text[:400]) from exc
    if not isinstance(parsed, dict):
        raise ModelCallError("bad_json", "顶层不是 JSON 对象: " + text[:200])
    return parsed
