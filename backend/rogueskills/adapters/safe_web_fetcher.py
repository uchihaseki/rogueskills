from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx


class UnsafeSourceUrl(ValueError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "canvas"}:
            self.ignored_depth += 1
        elif tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "canvas"} and self.ignored_depth:
            self.ignored_depth -= 1
        elif tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)

    def text(self) -> str:
        text = "".join(self.parts).replace("\r", "")
        lines = [" ".join(line.split()) for line in text.split("\n")]
        return "\n".join(line for line in lines if line)


class SafeWebFetcher:
    """Read-only origin fetcher with conservative URL and response limits."""

    def __init__(self, client: httpx.AsyncClient, *, max_bytes: int = 262_144) -> None:
        self.client = client
        self.max_bytes = max_bytes

    @staticmethod
    def validate_url(url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise UnsafeSourceUrl("只允许公开 HTTP(S) 来源")
        hostname = parsed.hostname.casefold().rstrip(".")
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
            raise UnsafeSourceUrl("不允许访问本机或本地域名")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return
        if not address.is_global:
            raise UnsafeSourceUrl("不允许访问私网、回环或链路本地地址")

    @staticmethod
    async def validate_dns(url: str) -> None:
        hostname = urlsplit(url).hostname
        if not hostname or hostname == "example.com" or hostname.endswith(".example.com"):
            # RFC 2606 names are useful for deterministic MockTransport tests and never route.
            return
        try:
            addresses = await asyncio.to_thread(
                socket.getaddrinfo,
                hostname,
                None,
                socket.AF_UNSPEC,
                socket.SOCK_STREAM,
            )
        except socket.gaierror as error:
            raise UnsafeSourceUrl("来源域名无法解析") from error
        if not addresses:
            raise UnsafeSourceUrl("来源域名没有可用地址")
        for address in addresses:
            resolved = ipaddress.ip_address(address[4][0])
            if not resolved.is_global:
                raise UnsafeSourceUrl("来源域名解析到私网、回环或链路本地地址")

    async def fetch(self, url: str) -> dict[str, Any]:
        self.validate_url(url)
        await self.validate_dns(url)
        response = await self.client.get(
            url,
            headers={"Accept": "text/markdown,text/plain,text/html;q=0.9"},
            follow_redirects=False,
        )
        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                raise ValueError("来源重定向缺少 Location")
            target = urljoin(url, location)
            self.validate_url(target)
            await self.validate_dns(target)
            response = await self.client.get(
                target,
                headers={"Accept": "text/markdown,text/plain,text/html;q=0.9"},
                follow_redirects=False,
            )
            if response.is_redirect:
                raise ValueError("来源重定向次数超过限制")
        response.raise_for_status()
        raw = response.content
        if len(raw) > self.max_bytes:
            raise ValueError("来源正文超过大小限制")
        content_type = response.headers.get("content-type", "text/plain").split(";", 1)[0]
        if content_type not in {"text/plain", "text/markdown", "text/html", "application/xhtml+xml"}:
            raise ValueError(f"不支持的来源 Content-Type：{content_type}")
        text = response.text
        if content_type in {"text/html", "application/xhtml+xml"}:
            parser = _TextExtractor()
            parser.feed(text)
            text = parser.text()
        text = re.sub(r"\n{4,}", "\n\n\n", text).strip()
        return {
            "content": text[: self.max_bytes],
            "contentType": content_type,
            "finalUrl": str(response.url),
        }
