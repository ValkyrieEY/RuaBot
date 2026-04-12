"""Runtime for Assistant mode message handling."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse

import httpx

from ..core.config import get_runtime_base_dir
from ..core.logger import get_logger
from .security import decrypt_secret

logger = get_logger(__name__)


DEFAULT_WAKE_WORDS = ("小易", "小艺", "ai", "AI", "/ai", "bot", "Bot")


def _data_dir() -> Path:
    path = get_runtime_base_dir() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _assistant_config_path() -> Path:
    return _data_dir() / "assistant_config.json"


def _assistant_audit_path() -> Path:
    return _data_dir() / "assistant_audit.jsonl"


def _assistant_memory_path() -> Path:
    return _data_dir() / "assistant_memory.json"


def _assistant_usage_path() -> Path:
    return _data_dir() / "assistant_usage.json"


class AssistantRuntime:
    """Handle incoming OneBot messages according to Assistant config."""

    def __init__(self) -> None:
        self._config_mtime: Optional[float] = None
        self._config: Dict[str, Any] = {}
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._semaphore_size: Optional[int] = None
        self._memory_lock = asyncio.Lock()
        self._usage_lock = asyncio.Lock()
        self._session_memory: Dict[str, List[Dict[str, str]]] = {}

    async def handle_message(self, payload: Dict[str, Any], onebot_adapter: Any) -> None:
        """Process a OneBot message and send an Assistant reply when policy allows it."""
        try:
            config = await self._load_config()
            system = self._dict(config.get("system"))
            if not system.get("enabled", False):
                return

            message_type = str(payload.get("message_type") or "")
            if message_type not in {"group", "private"}:
                return
            if bool(payload.get("is_self")):
                return

            raw_message = str(payload.get("raw_message") or payload.get("message") or "").strip()
            if not raw_message:
                return

            self_id = str(payload.get("self_id") or "")
            if self_id and str(payload.get("user_id") or "") == self_id:
                return

            policy = self._select_policy(config, payload, message_type)
            if not policy or not policy.get("enabled", False):
                return

            trigger_reason = await self._should_trigger(config, policy, raw_message, self_id, message_type, system)
            if not trigger_reason:
                return
            limited_reason = await self._rate_limit_reason(policy, payload, message_type)
            if limited_reason:
                await self._audit(config, payload, policy, raw_message, "", limited_reason, ok=False, error=limited_reason)
                return
            safety = self._safety_decision(self._clean_message(raw_message, policy), system)
            if not safety.get("allowed", True):
                reply = str(safety.get("reply") or "这条请求不适合由 Assistant 处理。")
                await self._send_reply(onebot_adapter, payload, message_type, reply)
                await self._audit(
                    config,
                    payload,
                    policy,
                    raw_message,
                    reply,
                    trigger_reason,
                    ok=False,
                    error=str(safety.get("reason") or "safety_block"),
                )
                return

            semaphore = self._get_semaphore(system)
            async with semaphore:
                reply = await self._generate_reply(config, policy, payload, raw_message, system, onebot_adapter)
                if not reply:
                    return
                await self._send_reply(onebot_adapter, payload, message_type, reply)
                await self._record_usage(policy, payload, message_type)
                await self._audit(config, payload, policy, raw_message, reply, trigger_reason, ok=True)
        except Exception as exc:
            logger.error(f"Assistant runtime failed: {exc}", exc_info=True)
            try:
                await self._audit({}, payload, {}, str(payload.get("raw_message") or ""), "", "error", ok=False, error=str(exc))
            except Exception:
                pass

    async def clear_memory(self, scope: str, target_id: str, memory_type: str) -> Dict[str, bool]:
        """Clear Assistant memory for a group/private target."""
        key = f"{scope}:{target_id}"
        cleared_session = False
        cleared_long = False

        if memory_type in {"session", "all"}:
            cleared_session = self._session_memory.pop(key, None) is not None

        if memory_type in {"long", "all"}:
            async with self._memory_lock:
                memory = await self._read_json(_assistant_memory_path(), {})
                long_store = memory.get("long", {}) if isinstance(memory, dict) else {}
                if isinstance(long_store, dict) and key in long_store:
                    long_store.pop(key, None)
                    memory["long"] = long_store
                    await self._write_json(_assistant_memory_path(), memory)
                    cleared_long = True

        return {"session": cleared_session, "long": cleared_long}

    async def _load_config(self) -> Dict[str, Any]:
        path = _assistant_config_path()
        if not path.exists():
            self._config = {}
            self._config_mtime = None
            return self._config

        mtime = path.stat().st_mtime
        if self._config_mtime == mtime:
            return self._config

        def read_config() -> Dict[str, Any]:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}

        self._config = await asyncio.to_thread(read_config)
        self._config_mtime = mtime
        return self._config

    def _select_policy(self, config: Dict[str, Any], payload: Dict[str, Any], message_type: str) -> Optional[Dict[str, Any]]:
        if message_type == "group":
            group_id = str(payload.get("group_id") or "")
            return self._find_by_id(config.get("groups"), group_id)

        user_id = str(payload.get("user_id") or "")
        policy = self._find_by_id(config.get("personal"), user_id)
        if not policy:
            return None
        return policy

    async def _should_trigger(
        self,
        config: Dict[str, Any],
        policy: Dict[str, Any],
        raw_message: str,
        self_id: str,
        message_type: str,
        system: Dict[str, Any],
    ) -> str:
        if message_type == "private":
            return "private"

        trigger = str(policy.get("trigger") or "mention")
        if trigger == "always":
            return "always"
        mentioned = self._is_mentioned(raw_message, self_id)
        if trigger == "mention" and mentioned:
            return "mention"
        if trigger == "keyword" and self._has_wake_word(raw_message, policy, system):
            return "keyword"
        if trigger == "prefix" and self._has_prefix(raw_message, policy):
            return "prefix"
        if trigger == "smart":
            if await self._smart_should_trigger(config, policy, raw_message, system):
                return "smart_ai"
        return ""

    async def _generate_reply(
        self,
        config: Dict[str, Any],
        policy: Dict[str, Any],
        payload: Dict[str, Any],
        raw_message: str,
        system: Dict[str, Any],
        onebot_adapter: Any,
    ) -> str:
        preset_name = str(policy.get("preset") or "")
        preset = self._find_by_name(config.get("presets"), preset_name)
        if preset and not preset.get("enabled", True):
            logger.debug(f"Assistant preset disabled, falling back to no preset: {preset_name}")
            preset = None

        prompt = self._compose_system_prompt(str((preset or {}).get("prompt") or ""), system)
        cleaned_message = self._clean_message(raw_message, policy)
        sender_name = self._sender_name(payload)
        chat_hint = self._chat_hint(payload)
        image_refs = self._extract_image_refs(raw_message)
        temperature = float((preset or {}).get("temperature", 0.4) or 0.4)
        errors: List[str] = []
        model_chain = self._model_chain(config, str(policy.get("model") or ""))
        if not model_chain:
            raise RuntimeError(f"Assistant model is missing: {policy.get('model') or ''}")

        for model in model_chain:
            model_id = str(model.get("id") or "")
            if not model.get("enabled", False):
                errors.append(f"{model_id}: model disabled")
                continue

            provider_name = str(model.get("provider") or "")
            provider = self._find_provider(config.get("providers"), provider_name)
            if not provider or not provider.get("enabled", False):
                errors.append(f"{model_id}: provider disabled or missing ({provider_name})")
                continue
            supports_images = self._model_supports_image(model)

            timeout = float(system.get("requestTimeout") or provider.get("timeout") or 60)
            try:
                image_data_urls = await self._resolve_image_data_urls(image_refs, onebot_adapter) if supports_images else []
                messages = await self._build_messages(
                    policy,
                    payload,
                    cleaned_message,
                    prompt,
                    sender_name,
                    chat_hint,
                    system,
                    image_data_urls,
                )
                reply = await self._call_model_api(
                    model=model,
                    provider=provider,
                    model_id=model_id,
                    messages=messages,
                    temperature=temperature,
                    timeout=timeout,
                )
                if reply:
                    await self._remember_exchange(policy, payload, cleaned_message, reply, system)
                    return reply
            except Exception as exc:
                errors.append(f"{model_id}: {exc}")

        raise RuntimeError("Assistant model routing failed: " + "; ".join(errors))

    async def _smart_should_trigger(
        self,
        config: Dict[str, Any],
        policy: Dict[str, Any],
        raw_message: str,
        system: Dict[str, Any],
    ) -> bool:
        cleaned_message = self._strip_at(raw_message) or raw_message.strip()
        if not cleaned_message:
            return False

        messages = [
            {
                "role": "system",
                "content": (
                    "你是群聊 AI 助手的触发判定器。只输出 YES 或 NO。"
                    "当消息明显是在请求机器人、AI、助手帮忙，或需要机器人回答时输出 YES；"
                    "普通闲聊、对其他人的回复、无明确求助的陈述输出 NO。"
                ),
            },
            {"role": "user", "content": f"群聊消息：{cleaned_message}\n是否应该触发助手回复？"},
        ]

        for model in self._model_chain(config, str(policy.get("model") or "")):
            if not model.get("enabled", False):
                continue
            provider = self._find_provider(config.get("providers"), str(model.get("provider") or ""))
            if not provider or not provider.get("enabled", False):
                continue
            timeout = min(float(system.get("requestTimeout") or provider.get("timeout") or 60), 12.0)
            try:
                reply = await self._call_model_api(
                    model=model,
                    provider=provider,
                    model_id=str(model.get("id") or ""),
                    messages=messages,
                    temperature=0.0,
                    timeout=timeout,
                )
                normalized = reply.strip().lower()
                return normalized.startswith("yes") or normalized.startswith("y") or normalized.startswith("是")
            except Exception as exc:
                logger.warning(f"Assistant smart trigger failed: {exc}")
                continue

        return False

    async def _build_messages(
        self,
        policy: Dict[str, Any],
        payload: Dict[str, Any],
        cleaned_message: str,
        prompt: str,
        sender_name: str,
        chat_hint: str,
        system: Dict[str, Any],
        image_data_urls: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        user_content = (
            f"聊天场景：{chat_hint}\n"
            f"发送者：{sender_name} ({payload.get('user_id', '')})\n"
            f"用户消息：{cleaned_message}"
        )
        messages: List[Dict[str, Any]] = []
        if str(prompt or "").strip():
            messages.append({"role": "system", "content": prompt})
        messages.extend(await self._memory_messages(policy, payload, system))
        if image_data_urls:
            content: List[Dict[str, Any]] = [{"type": "text", "text": user_content}]
            content.extend(
                {"type": "image_url", "image_url": {"url": data_url}}
                for data_url in image_data_urls[:6]
            )
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_content})
        return messages

    async def _memory_messages(
        self,
        policy: Dict[str, Any],
        payload: Dict[str, Any],
        system: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        mode = self._memory_mode(policy, system)
        if mode == "off":
            return []

        key = self._memory_key(policy, payload)
        if mode == "session":
            records = self._session_memory.get(key, [])
            return self._conversation_messages(records[-8:])

        async with self._memory_lock:
            memory = await self._read_json(_assistant_memory_path(), {})

        long_memory = self._long_memory_bucket(memory, key)
        records = long_memory.get("messages", [])
        messages: List[Dict[str, str]] = []

        summary = str(long_memory.get("summary") or "").strip()
        if summary:
            messages.append({"role": "system", "content": f"长期记忆摘要：{summary}"})

        facts = long_memory.get("facts", [])
        if isinstance(facts, list):
            fact_text = "\n".join(str(item) for item in facts[-30:] if str(item).strip())
            if fact_text:
                messages.append({"role": "system", "content": f"长期记忆事实：\n{fact_text}"})

        if isinstance(records, list):
            messages.extend(self._conversation_messages(records[-16:]))
        return messages

    async def _remember_exchange(
        self,
        policy: Dict[str, Any],
        payload: Dict[str, Any],
        user_message: str,
        assistant_reply: str,
        system: Dict[str, Any],
    ) -> None:
        mode = self._memory_mode(policy, system)
        if mode == "off":
            return

        key = self._memory_key(policy, payload)
        now = datetime.now().isoformat()

        if mode == "session":
            records = self._session_memory.setdefault(key, [])
            records.extend(
                [
                    {"role": "user", "content": user_message, "time": now},
                    {"role": "assistant", "content": assistant_reply, "time": now},
                ]
            )
            self._session_memory[key] = records[-16:]
            return

        async with self._memory_lock:
            memory = await self._read_json(_assistant_memory_path(), {})
            if not isinstance(memory, dict):
                memory = {}
            long_store = memory.setdefault("long", {})
            if not isinstance(long_store, dict):
                long_store = {}
                memory["long"] = long_store
            bucket = long_store.setdefault(key, {"summary": "", "facts": [], "messages": []})
            if not isinstance(bucket, dict):
                bucket = {"summary": "", "facts": [], "messages": []}
                long_store[key] = bucket
            records = bucket.setdefault("messages", [])
            if not isinstance(records, list):
                records = []
                bucket["messages"] = records
            records.extend(
                [
                    {"role": "user", "content": user_message, "time": now},
                    {"role": "assistant", "content": assistant_reply, "time": now},
                ]
            )
            bucket["messages"] = records[-80:]
            bucket["facts"] = self._merge_facts(bucket.get("facts"), self._extract_facts(user_message))
            bucket["summary"] = self._build_long_summary(str(bucket.get("summary") or ""), bucket["facts"], bucket["messages"])
            bucket["updated_at"] = now
            await self._write_json(_assistant_memory_path(), memory)

    async def _rate_limit_reason(self, policy: Dict[str, Any], payload: Dict[str, Any], message_type: str) -> str:
        cooldown = max(0, int(policy.get("cooldown") or 0))
        daily_limit = max(0, int(policy.get("dailyLimit") or 0))
        if cooldown == 0 and daily_limit == 0:
            return ""

        key = self._usage_key(policy, payload, message_type)
        today = datetime.now().date().isoformat()
        now_ts = datetime.now().timestamp()

        async with self._usage_lock:
            usage = await self._read_json(_assistant_usage_path(), {})
            day_usage = usage.get(today, {}) if isinstance(usage, dict) else {}
            entry = day_usage.get(key, {}) if isinstance(day_usage, dict) else {}
            last_ts = float(entry.get("last_ts") or 0)
            count = int(entry.get("count") or 0)

        if cooldown and last_ts and now_ts - last_ts < cooldown:
            return f"cooldown:{cooldown}s"
        if daily_limit and count >= daily_limit:
            return f"daily_limit:{daily_limit}"
        return ""

    async def _record_usage(self, policy: Dict[str, Any], payload: Dict[str, Any], message_type: str) -> None:
        key = self._usage_key(policy, payload, message_type)
        today = datetime.now().date().isoformat()
        now_ts = datetime.now().timestamp()

        async with self._usage_lock:
            usage = await self._read_json(_assistant_usage_path(), {})
            if not isinstance(usage, dict):
                usage = {}
            usage = {today: usage.get(today, {}) if isinstance(usage.get(today), dict) else {}}
            day_usage = usage[today]
            entry = day_usage.get(key, {}) if isinstance(day_usage.get(key), dict) else {}
            entry["count"] = int(entry.get("count") or 0) + 1
            entry["last_ts"] = now_ts
            day_usage[key] = entry
            await self._write_json(_assistant_usage_path(), usage)

    async def _call_model_api(
        self,
        model: Dict[str, Any],
        provider: Dict[str, Any],
        model_id: str,
        messages: List[Dict[str, Any]],
        temperature: float,
        timeout: float,
    ) -> str:
        api_format = self._model_api_format(model, provider)
        if api_format == "gemini":
            return await self._call_gemini(
                provider=provider,
                model_id=model_id,
                messages=messages,
                temperature=temperature,
                timeout=timeout,
            )
        return await self._call_openai_compatible(
            provider=provider,
            model_id=model_id,
            messages=messages,
            temperature=temperature,
            timeout=timeout,
        )

    async def _call_openai_compatible(
        self,
        provider: Dict[str, Any],
        model_id: str,
        messages: List[Dict[str, Any]],
        temperature: float,
        timeout: float,
    ) -> str:
        base_url = str(provider.get("baseUrl") or "").rstrip("/")
        if not base_url:
            raise RuntimeError("Assistant provider baseUrl is empty")
        api_key = decrypt_secret(str(provider.get("apiKey") or ""))
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            if isinstance(data, dict)
            else ""
        )
        return str(content).strip()

    async def _call_gemini(
        self,
        provider: Dict[str, Any],
        model_id: str,
        messages: List[Dict[str, Any]],
        temperature: float,
        timeout: float,
    ) -> str:
        base_url = str(provider.get("baseUrl") or "").rstrip("/")
        if not base_url:
            raise RuntimeError("Assistant provider baseUrl is empty")
        api_key = decrypt_secret(str(provider.get("apiKey") or ""))
        endpoint = self._gemini_endpoint(base_url, model_id)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["x-goog-api-key"] = api_key

        payload = self._messages_to_gemini_payload(messages, temperature)
        params = {"key": api_key} if api_key else None

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, headers=headers, params=params, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates", []) if isinstance(data, dict) else []
        parts = (
            candidates[0].get("content", {}).get("parts", [])
            if candidates and isinstance(candidates[0], dict)
            else []
        )
        texts = [str(part.get("text") or "") for part in parts if isinstance(part, dict) and part.get("text")]
        return "\n".join(texts).strip()

    @staticmethod
    def _gemini_endpoint(base_url: str, model_id: str) -> str:
        if "{model}" in base_url:
            return base_url.format(model=model_id, model_id=model_id)
        if base_url.endswith(":generateContent"):
            return base_url
        if base_url.rstrip("/").endswith("/models"):
            return f"{base_url.rstrip('/')}/{model_id}:generateContent"
        return f"{base_url.rstrip('/')}/models/{model_id}:generateContent"

    def _messages_to_gemini_payload(self, messages: List[Dict[str, Any]], temperature: float) -> Dict[str, Any]:
        system_parts: List[Dict[str, Any]] = []
        contents: List[Dict[str, Any]] = []

        for message in messages:
            role = str(message.get("role") or "user")
            parts = self._gemini_parts_from_content(message.get("content"))
            if not parts:
                continue
            if role == "system":
                system_parts.extend(parts)
                continue
            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": parts,
            })

        payload: Dict[str, Any] = {
            "contents": contents or [{"role": "user", "parts": [{"text": ""}]}],
            "generationConfig": {"temperature": temperature},
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
        return payload

    def _gemini_parts_from_content(self, content: Any) -> List[Dict[str, Any]]:
        if isinstance(content, str):
            text = content.strip()
            return [{"text": text}] if text else []

        parts: List[Dict[str, Any]] = []
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    text = str(item.get("text") or "").strip()
                    if text:
                        parts.append({"text": text})
                    continue
                if item.get("type") == "image_url":
                    image_url = item.get("image_url")
                    url = image_url.get("url") if isinstance(image_url, dict) else ""
                    inline = self._data_url_to_gemini_inline(str(url or ""))
                    if inline:
                        parts.append({"inline_data": inline})
        return parts

    @staticmethod
    def _data_url_to_gemini_inline(data_url: str) -> Optional[Dict[str, str]]:
        match = re.match(r"^data:([^;,]+);base64,(.*)$", data_url, re.DOTALL)
        if not match:
            return None
        mime_type = match.group(1) or "image/jpeg"
        data = match.group(2) or ""
        return {"mime_type": mime_type, "data": data}

    @staticmethod
    def _model_api_format(model: Dict[str, Any], provider: Dict[str, Any]) -> str:
        value = str(model.get("apiFormat") or model.get("format") or model.get("api_format") or "").strip().lower()
        if value in {"gemini", "genimi", "google"}:
            return "gemini"
        if value in {"openai", "openai-compatible", "compatible"}:
            return "openai"

        hint = " ".join(
            str(part or "")
            for part in (provider.get("name"), provider.get("id"), provider.get("baseUrl"))
        ).lower()
        return "gemini" if "gemini" in hint or "googleapis" in hint else "openai"

    @staticmethod
    def _model_supports_image(model: Dict[str, Any]) -> bool:
        capabilities = model.get("capabilities")
        values = capabilities if isinstance(capabilities, list) else re.split(r"[,，/、\s]+", str(model.get("capability") or ""))
        normalized = {str(item or "").strip().lower() for item in values}
        return bool(normalized & {"image", "vision", "图片", "图像", "视觉", "多模态"})

    async def _resolve_image_data_urls(self, image_refs: List[str], onebot_adapter: Any) -> List[str]:
        data_urls: List[str] = []
        for media_ref in image_refs[:6]:
            try:
                data_url = await self._media_ref_to_data_url(media_ref, onebot_adapter)
                if data_url:
                    data_urls.append(data_url)
            except Exception as exc:
                logger.warning(f"Assistant image resolve failed: {media_ref[:120]} error={exc}")
        return data_urls

    async def _media_ref_to_data_url(self, media_ref: str, onebot_adapter: Any) -> Optional[str]:
        media_ref = str(media_ref or "").strip()
        if not media_ref:
            return None
        if media_ref.startswith("data:image/"):
            try:
                from ..ui.image_cache import get_image_cache_manager
                await get_image_cache_manager().save_data_url_media(media_ref, media_kind="image")
            except Exception as exc:
                logger.debug(f"Assistant data image cache skipped: {exc}")
            return media_ref
        if media_ref.startswith("base64://"):
            data_url = f"data:image/jpeg;base64,{media_ref[len('base64://'):]}"
            try:
                from ..ui.image_cache import get_image_cache_manager
                await get_image_cache_manager().save_data_url_media(data_url, media_kind="image")
            except Exception as exc:
                logger.debug(f"Assistant base64 image cache skipped: {exc}")
            return data_url

        resolved = media_ref
        try:
            from ..ui.image_cache import get_image_cache_manager
            cached_path = await get_image_cache_manager().download_and_cache_media(
                media_ref,
                onebot_adapter=onebot_adapter,
                media_kind="image",
            )
            if cached_path:
                cached_data_url = await self._file_to_data_url(Path(cached_path))
                if cached_data_url:
                    return cached_data_url
        except Exception as exc:
            logger.debug(f"Assistant image cache unavailable for {media_ref[:120]}: {exc}")

        if not (resolved.startswith("http://") or resolved.startswith("https://") or resolved.startswith("file://")):
            resolved = await self._resolve_onebot_image_ref(resolved, onebot_adapter) or resolved

        if resolved.startswith("file://"):
            path = Path(unquote(urlparse(resolved).path))
            if not path.exists() and resolved.startswith("file:///"):
                path = Path(unquote(resolved.replace("file:///", "", 1)))
            return await self._file_to_data_url(path)

        if resolved.startswith("http://") or resolved.startswith("https://"):
            headers = {
                "Referer": "https://qzone.qq.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
                response = await client.get(resolved, headers=headers)
                response.raise_for_status()
                content_type = (response.headers.get("content-type") or "image/jpeg").split(";")[0]
                if not content_type.startswith("image/"):
                    content_type = "image/jpeg"
                return f"data:{content_type};base64,{base64.b64encode(response.content).decode('ascii')}"
        return None

    @staticmethod
    async def _file_to_data_url(path: Path) -> Optional[str]:
        if not path.exists() or not path.is_file():
            return None
        raw = await asyncio.to_thread(path.read_bytes)
        mime_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
        return f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"

    async def _resolve_onebot_image_ref(self, file_ref: str, onebot_adapter: Any) -> Optional[str]:
        if not onebot_adapter:
            return None
        try:
            result = await onebot_adapter.call_api("get_image", {"file": file_ref}, source="assistant")
            if isinstance(result, dict):
                data = result.get("data", result)
                if isinstance(data, dict):
                    return str(data.get("url") or data.get("file") or "").strip() or None
        except Exception as exc:
            logger.debug(f"Assistant get_image unavailable for {file_ref}: {exc}")
        return None

    async def _send_reply(self, onebot_adapter: Any, payload: Dict[str, Any], message_type: str, reply: str) -> None:
        if message_type == "group":
            group_id = int(payload.get("group_id"))
            await onebot_adapter.call_api(
                "send_group_msg",
                {"group_id": group_id, "message": reply},
                source="assistant",
            )
            return

        user_id = int(payload.get("user_id"))
        await onebot_adapter.call_api(
            "send_private_msg",
            {"user_id": user_id, "message": reply},
            source="assistant",
        )

    async def _audit(
        self,
        config: Dict[str, Any],
        payload: Dict[str, Any],
        policy: Dict[str, Any],
        raw_message: str,
        reply: str,
        trigger_reason: str,
        ok: bool,
        error: str = "",
    ) -> None:
        system = self._dict(config.get("system"))
        if config and not system.get("auditEnabled", True):
            return

        record = {
            "time": datetime.now().isoformat(),
            "ok": ok,
            "error": error,
            "message_type": payload.get("message_type"),
            "group_id": str(payload.get("group_id") or ""),
            "user_id": str(payload.get("user_id") or ""),
            "policy_id": str(policy.get("id") or ""),
            "model": str(policy.get("model") or ""),
            "preset": str(policy.get("preset") or ""),
            "trigger": trigger_reason,
            "raw_message": raw_message,
            "reply": reply,
        }

        def write_record() -> None:
            with open(_assistant_audit_path(), "a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")

        await asyncio.to_thread(write_record)

    def _get_semaphore(self, system: Dict[str, Any]) -> asyncio.Semaphore:
        size = max(1, int(system.get("maxConcurrent") or 1))
        if self._semaphore is None or self._semaphore_size != size:
            self._semaphore = asyncio.Semaphore(size)
            self._semaphore_size = size
        return self._semaphore

    def _safety_decision(self, text: str, system: Dict[str, Any]) -> Dict[str, Any]:
        level = str(system.get("safetyLevel") or "balanced")
        normalized = text.strip().lower()
        if not normalized:
            return {"allowed": True}

        checks = [
            (
                "self_harm",
                [
                    r"自杀|结束生命|怎么死|割腕|上吊|跳楼",
                ],
            ),
            (
                "sexual_minors",
                [
                    r"未成年.*(?:性|裸|黄片|约炮)|幼女|萝莉.*(?:裸|性)",
                ],
            ),
            (
                "cyber_abuse",
                [
                    r"勒索软件|木马|后门|免杀|盗取.*(?:密码|账号|cookie|token)|钓鱼网站|shellcode",
                ],
            ),
            (
                "weapons_explosives",
                [
                    r"炸药|爆炸物|制作.*(?:枪|炸弹)|制毒",
                ],
            )
        ]

        if level in {"balanced", "strict"}:
            checks.append(
                (
                    "dangerous_or_illegal",
                    [
                        r"杀人|下毒|绑架|抢劫|贩毒|走私|开锁教程",
                        r"人肉|社工库|查.*(?:身份证|手机号|开房|住址|定位)",
                        r"伪造(?:身份证|证件|发票)|洗钱|套现",
                        r"ddos|撞库|爆破|脱库|绕过.*验证码",
                    ],
                )
            )

        if level == "strict":
            checks.append(
                (
                    "strict_policy",
                    [
                        r"色情|黄色|成人内容|裸聊|约炮|成人视频",
                        r"辱骂|骂人|喷人|网暴|挂人",
                        r"越狱|忽略.*(?:规则|限制|系统提示)|绕过.*(?:安全|限制)",
                    ],
                )
            )

        for reason, patterns in checks:
            if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns):
                return {
                    "allowed": False,
                    "reason": f"safety:{level}:{reason}",
                    "reply": self._safety_reply(level, reason),
                }

        return {"allowed": True}

    @staticmethod
    def _safety_reply(level: str, reason: str) -> str:
        if reason == "self_harm":
            return "这个请求涉及高风险内容，我不能提供具体做法。如果你现在有现实危险或伤害自己的冲动，请立刻联系身边可信的人或当地紧急援助。"
        if reason in {"cyber_abuse", "weapons_explosives", "dangerous_or_illegal", "sexual_minors"}:
            return "这个请求涉及违法、隐私或危险操作，我不能提供具体做法。但可以帮你改成安全、合规的咨询方向。"
        if level == "strict":
            return "这条内容在当前严格安全策略下不适合处理。我可以换个安全方向帮你整理信息、做解释或提供替代方案。"
        return "这个请求涉及违法、隐私或危险操作，我不能提供具体做法。但可以帮你改成安全、合规的咨询方向。"

    def _compose_system_prompt(self, prompt: str, system: Dict[str, Any]) -> str:
        instruction = self._safety_instruction(system)
        prompt = str(prompt or "").strip()
        if prompt and instruction:
            return f"{prompt}\n\n{instruction}"
        return prompt or instruction

    @staticmethod
    def _safety_instruction(system: Dict[str, Any]) -> str:
        level = str(system.get("safetyLevel") or "balanced")
        if level == "low":
            return (
                "安全策略：宽松。除非用户请求自伤、伤害他人、未成年人性内容、恶意网络攻击、武器爆炸物或明显违法高危操作，"
                "否则尽量正常帮助；遇到高危请求时拒绝具体步骤，并提供安全替代建议。"
            )
        if level == "strict":
            return (
                "安全策略：严格。拒绝提供违法、暴力、隐私侵犯、恶意网络攻击、成人色情、辱骂骚扰、越狱绕过和其他高风险内容；"
                "回复要克制、合规，并主动给出安全替代方案。"
            )
        return (
            "安全策略：平衡。拒绝提供违法、危险操作、隐私侵犯、恶意网络攻击、自伤或伤害他人的可执行指导；"
            "可以提供科普、风险解释、防护建议和合规替代方案。"
        )

    def _model_chain(self, config: Dict[str, Any], model_id: str) -> List[Dict[str, Any]]:
        chain: List[Dict[str, Any]] = []
        visited = set()
        current = model_id

        while current and current not in visited and len(chain) < 5:
            visited.add(current)
            model = self._find_by_id(config.get("models"), current)
            if not model:
                break
            chain.append(model)
            current = str(model.get("fallback") or "")

        return chain

    @staticmethod
    def _memory_mode(policy: Dict[str, Any], system: Dict[str, Any]) -> str:
        if not system.get("memoryEnabled", False):
            return "off"
        mode = str(policy.get("memory") or "off")
        return mode if mode in {"off", "session", "long"} else "off"

    @staticmethod
    def _memory_key(policy: Dict[str, Any], payload: Dict[str, Any]) -> str:
        message_type = str(payload.get("message_type") or "")
        if message_type == "group":
            return f"group:{payload.get('group_id') or policy.get('id') or ''}"
        return f"private:{payload.get('user_id') or policy.get('id') or ''}"

    @staticmethod
    def _long_memory_bucket(memory: Dict[str, Any], key: str) -> Dict[str, Any]:
        long_store = memory.get("long", {}) if isinstance(memory, dict) else {}
        if isinstance(long_store, dict) and isinstance(long_store.get(key), dict):
            return long_store[key]

        legacy_conversations = memory.get("conversations", {}) if isinstance(memory, dict) else {}
        legacy_records = legacy_conversations.get(key, []) if isinstance(legacy_conversations, dict) else []
        return {
            "summary": "",
            "facts": [],
            "messages": legacy_records if isinstance(legacy_records, list) else [],
        }

    @staticmethod
    def _conversation_messages(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            role = str(record.get("role") or "")
            content = str(record.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        return messages

    @staticmethod
    def _extract_facts(text: str) -> List[str]:
        facts: List[str] = []
        cleaned = text.strip()
        if not cleaned:
            return facts

        patterns = [
            r"(?:我|我的)(名字|昵称|生日|城市|学校|职业|工作|爱好|偏好|常用模型|喜欢|不喜欢)(?:是|叫|为|:|：)?\s*([^，。！？\n]{1,60})",
            r"(?:请|帮我)?记住[:：]?\s*([^。！？\n]{2,80})",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, cleaned):
                if len(match.groups()) == 2:
                    facts.append(f"{match.group(1)}：{match.group(2).strip()}")
                else:
                    facts.append(match.group(1).strip())

        return facts[:8]

    @staticmethod
    def _merge_facts(existing: Any, new_facts: List[str]) -> List[str]:
        merged: List[str] = []
        for fact in existing if isinstance(existing, list) else []:
            value = str(fact).strip()
            if value and value not in merged:
                merged.append(value)
        for fact in new_facts:
            value = str(fact).strip()
            if value and value not in merged:
                merged.append(value)
        return merged[-30:]

    @staticmethod
    def _build_long_summary(existing_summary: str, facts: Any, records: Any) -> str:
        fact_list = [str(item).strip() for item in facts if str(item).strip()] if isinstance(facts, list) else []
        user_messages = [
            str(item.get("content") or "").strip()
            for item in records[-20:]
            if isinstance(item, dict) and item.get("role") == "user" and str(item.get("content") or "").strip()
        ] if isinstance(records, list) else []

        parts: List[str] = []
        if fact_list:
            parts.append("已知事实：" + "；".join(fact_list[-10:]))
        if user_messages:
            parts.append("近期关注：" + "；".join(user_messages[-6:]))
        summary = "。".join(parts).strip("。")
        return summary[:1200] if summary else existing_summary[:1200]

    @staticmethod
    def _usage_key(policy: Dict[str, Any], payload: Dict[str, Any], message_type: str) -> str:
        if message_type == "group":
            return f"group:{payload.get('group_id') or policy.get('id') or ''}"
        return f"private:{payload.get('user_id') or policy.get('id') or ''}"

    @staticmethod
    async def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
        if not path.exists():
            return dict(default)

        def read_file() -> Dict[str, Any]:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else dict(default)

        try:
            return await asyncio.to_thread(read_file)
        except json.JSONDecodeError:
            logger.warning(f"Assistant JSON store is invalid: {path}")
            return dict(default)

    @staticmethod
    async def _write_json(path: Path, data: Dict[str, Any]) -> None:
        def write_file() -> None:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)

        await asyncio.to_thread(write_file)

    @staticmethod
    def _find_by_id(items: Any, item_id: str) -> Optional[Dict[str, Any]]:
        if not isinstance(items, list):
            return None
        for item in items:
            if isinstance(item, dict) and str(item.get("id") or "") == str(item_id):
                return item
        return None

    @staticmethod
    def _find_by_name(items: Any, name: str) -> Optional[Dict[str, Any]]:
        if not isinstance(items, list):
            return None
        for item in items:
            if isinstance(item, dict) and str(item.get("name") or "") == str(name):
                return item
        return None

    @staticmethod
    def _find_provider(items: Any, provider_name: str) -> Optional[Dict[str, Any]]:
        if not isinstance(items, list):
            return None
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "") == provider_name or str(item.get("id") or "") == provider_name:
                return item
        return None

    @staticmethod
    def _dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _is_mentioned(raw_message: str, self_id: str) -> bool:
        if self_id and f"[CQ:at,qq={self_id}]" in raw_message:
            return True
        return "[CQ:at,qq=all]" in raw_message

    @staticmethod
    def _has_wake_word(raw_message: str, policy: Dict[str, Any], system: Dict[str, Any]) -> bool:
        normalized = raw_message.strip()
        configured = str(policy.get("keywords") or system.get("wakeWords") or "")
        words = AssistantRuntime._split_terms(configured) or list(DEFAULT_WAKE_WORDS)
        return any(word in normalized for word in words)

    @staticmethod
    def _has_prefix(raw_message: str, policy: Dict[str, Any]) -> bool:
        text = AssistantRuntime._strip_at(raw_message)
        prefixes = AssistantRuntime._split_terms(str(policy.get("prefixes") or ""))
        return any(prefix and text.startswith(prefix) for prefix in prefixes)

    @staticmethod
    def _clean_message(raw_message: str, policy: Optional[Dict[str, Any]] = None) -> str:
        text = AssistantRuntime._strip_at(raw_message)
        text = re.sub(r"\[CQ:image,[^\]]+\]", "[图片]", text)
        text = re.sub(r"\[CQ:[^\]]+\]", "", text)
        if policy and str(policy.get("trigger") or "") in {"prefix", "smart"}:
            for prefix in AssistantRuntime._split_terms(str(policy.get("prefixes") or "")):
                if prefix and text.startswith(prefix):
                    return text[len(prefix):].strip() or text
        return text.strip() or raw_message

    @staticmethod
    def _strip_at(raw_message: str) -> str:
        text = re.sub(r"\[CQ:at,qq=[^\]]+\]", "", raw_message)
        return text.strip()

    @staticmethod
    def _extract_image_refs(raw_message: str) -> List[str]:
        refs: List[str] = []

        def parse_params(params_str: str) -> Dict[str, str]:
            params: Dict[str, str] = {}
            allowed_keys = {"file", "url", "summary", "sub_type"}
            key_pattern = re.compile(r"(?:^|,)([A-Za-z_][A-Za-z0-9_-]*)=")
            key_matches = [m for m in key_pattern.finditer(params_str) if m.group(1).strip() in allowed_keys]
            for idx, match in enumerate(key_matches):
                key = match.group(1).strip()
                value_start = match.end()
                value_end = key_matches[idx + 1].start() if idx + 1 < len(key_matches) else len(params_str)
                value = params_str[value_start:value_end].strip()
                if value.endswith(","):
                    value = value[:-1]
                if key and value:
                    params[key] = value
            return params

        for match in re.finditer(r"\[CQ:image,([^\]]+)\]", raw_message or ""):
            params = parse_params(match.group(1))
            media_ref = str(params.get("url") or params.get("file") or "").strip()
            if media_ref:
                refs.append(media_ref)
        return refs[:6]

    @staticmethod
    def _split_terms(value: str) -> List[str]:
        return [item.strip() for item in re.split(r"[,，\n]+", value) if item.strip()]

    @staticmethod
    def _sender_name(payload: Dict[str, Any]) -> str:
        sender = payload.get("sender")
        if isinstance(sender, dict):
            return str(sender.get("card") or sender.get("nickname") or "未知用户")
        return "未知用户"

    @staticmethod
    def _chat_hint(payload: Dict[str, Any]) -> str:
        if str(payload.get("message_type") or "") == "group":
            return f"群聊 {payload.get('group_id', '')}"
        return "私聊"


_assistant_runtime: Optional[AssistantRuntime] = None


def get_assistant_runtime() -> AssistantRuntime:
    global _assistant_runtime
    if _assistant_runtime is None:
        _assistant_runtime = AssistantRuntime()
    return _assistant_runtime
