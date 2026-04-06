"""Slack Bot Token 기반 알림 발송 모듈"""
from typing import Optional, List

import httpx

from config import SLACK_BOT_TOKEN, SLACK_CHANNEL


class SlackBotNotifier:
    """Slack Bot Token API를 사용한 메시지 발송 클래스."""

    BASE_URL = "https://slack.com/api"

    def __init__(
        self,
        token: Optional[str] = None,
        channel: Optional[str] = None,
    ):
        self.token = token or SLACK_BOT_TOKEN
        self.channel = channel or SLACK_CHANNEL

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    async def send_message(self, text: str, channel: Optional[str] = None) -> dict:
        """Slack 채널에 메시지를 전송한다."""
        if not self.is_configured:
            return {"ok": False, "error": "SLACK_BOT_TOKEN 미설정 — 시뮬레이션 모드"}

        payload = {
            "channel": channel or self.channel,
            "text": text,
            "mrkdwn": True,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat.postMessage",
                headers=self._headers,
                json=payload,
            )
            return resp.json()

    async def send_blocks(
        self,
        blocks: List[dict],
        text: str = "",
        channel: Optional[str] = None,
    ) -> dict:
        """Block Kit 형식으로 메시지를 전송한다."""
        if not self.is_configured:
            return {"ok": False, "error": "SLACK_BOT_TOKEN 미설정 — 시뮬레이션 모드"}

        payload = {
            "channel": channel or self.channel,
            "text": text,
            "blocks": blocks,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat.postMessage",
                headers=self._headers,
                json=payload,
            )
            return resp.json()
