# -*- coding: utf-8 -*-
"""
洛克王国宠物查询插件
功能：精灵查询、蛋组查询、孵蛋预测
插件端执行所有匹配和模糊搜索，仅校验通过的数据发送到计算服务
"""
import asyncio
import json
import os
import re as _re
from pathlib import Path

import aiohttp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

_PLUGIN_DIR = Path(__file__).resolve().parent
_DATA_PATH = _PLUGIN_DIR / "spirit_data.json"


def load_spirit_data() -> dict:
    if not _DATA_PATH.exists():
        return {"spirits": {}, "egg_groups": {}, "spirit_names": []}
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@register(
    "astrbot_plugin_rocopetconfirm_cinene",
    "Cinene",
    "洛克王国：世界精灵数据查询、孵蛋预测、蛋组查询。本地匹配+云端计算+图片渲染。",
    "1.3.0",
)
class RocPetConfirmPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}
        self.data = load_spirit_data()
        self.spirits: dict = self.data.get("spirits", {})
        self.egg_groups: list = list(self.data.get("egg_groups", {}).keys())
        self.spirit_names: list = self.data.get("spirit_names", [])
        self.api_url = self.config.get(
            "api_url", "https://cinene.cloud/api/compute"
        )
        self.trigger = self.config.get("trigger_word", "查询 ")
        self.pinyin_map: dict = self.data.get("pinyin_map", {})
        self.enable_spirit = self.config.get("enable_spirit", True)
        self.enable_egg_group = self.config.get("enable_egg_group", True)
        self.enable_predict = self.config.get("enable_predict", True)
        self.enable_render_image = self.config.get("enable_render_image", True)
        logger.info(
            f"插件加载: {len(self.spirits)} 精灵, {len(self.egg_groups)} 蛋组, "
            f"触发词='{self.trigger}'"
        )

    # ---------- 本地匹配引擎 ----------

    def _input_to_pinyin(self, text: str) -> str:
        """用拼音映射表将输入转为拼音字符串"""
        result = []
        for ch in text:
            if '\u4e00' <= ch <= '\u9fff':
                result.append(self.pinyin_map.get(ch, ch))
            else:
                result.append(ch.lower())
        return ''.join(result)

    def _fuzzy_match_spirit(self, keyword: str) -> list:
        """模糊匹配精灵名"""
        kw = keyword.lower().strip()
        if kw in self.spirits:
            return [kw]
        candidates = [n for n in self.spirit_names if kw in n.lower()]
        candidates.sort(key=len)
        if candidates:
            return candidates[:8]
        # 拼音匹配（查表，不需 pypinyin）
        input_py = self._input_to_pinyin(keyword)
        if input_py != kw:
            for n in self.spirit_names:
                info = self.spirits.get(n, {})
                name_py = info.get("name_pinyin", "")
                if not name_py:
                    continue
                if input_py == name_py or input_py in name_py or name_py in input_py:
                    candidates.append(n)
            if candidates:
                return candidates[:8]
        # 拆字匹配
        for ch in kw:
            sub = [n for n in self.spirit_names if ch in n.lower()]
            if sub:
                return sub[:8]
        return []

    def _fuzzy_match_egg_group(self, keyword: str) -> list:
        """模糊匹配蛋组，要求蛋组名在关键词中"""
        kw = keyword.lower().strip()
        if kw in self.egg_groups:
            return [kw]
        candidates = [g for g in self.egg_groups if g.lower() in kw]
        if candidates:
            return candidates
        return []

    def _try_match(self, text: str) -> dict:
        """
        尝试匹配输入，返回:
          {"match": True/False, "attribute": "...", "data": "...", "suggestion": "..."}
        - match=False 时 suggestion 为推荐文本
        - match=True 时 attribute/data 供发送计算服务
        """
        text = text.strip()
        if not text:
            return {"match": False, "suggestion": "请输入查询内容"}

        # --- 预测：两个数字 ---
        if self.enable_predict:
            parts = text.split()
            num_parts = [p for p in parts if p.replace(".", "").replace("-", "").isdigit()]
            if len(num_parts) == 2 and len(parts) == 2:
                return {"match": True, "attribute": "孵蛋预测", "data": " ".join(num_parts)}
        else:
            parts = text.split()

        # --- 蛋组匹配 ---
        if self.enable_egg_group:
            matched_groups = self._fuzzy_match_egg_group(text)
            if matched_groups:
                # 多蛋组交集: 输入包含 / 或 x 且每组都匹配
                sep = _re.split(r"[/xX\u00d7\s]+", text)
                group_keys = []
                for s in sep:
                    s = s.strip()
                    if not s:
                        continue
                    g = self._fuzzy_match_egg_group(s)
                    if g:
                        group_keys.append(g[0])
                    else:
                        group_keys = []
                        break
                if len(group_keys) >= 2:
                    return {"match": True, "attribute": "\u86cb\u7ec4\u67e5\u8be2", "data": "/".join(group_keys)}
                # \u5355\u86cb\u7ec4
                return {"match": True, "attribute": "\u86cb\u7ec4\u67e5\u8be2", "data": matched_groups[0]}


        # --- 精灵名称匹配 ---
        # 带体重: "精灵名 体重数值"
        if len(parts) >= 2:
            last = parts[-1]
            if last.replace(".", "").replace("-", "").isdigit():
                name_part = " ".join(parts[:-1])
                matched_names = self._fuzzy_match_spirit(name_part)
                if len(matched_names) == 1:
                    return {
                        "match": True,
                        "attribute": "精灵查询",
                        "data": f"{matched_names[0]} {last}",
                    }
                elif matched_names:
                    return {"match": True, "attribute": "精灵查询", "data": name_part}

        # 纯名称
        matched_names = self._fuzzy_match_spirit(text)
        if matched_names:
            if len(matched_names) == 1:
                return {"match": True, "attribute": "精灵查询", "data": matched_names[0]}
            # 多个匹配→发给服务器处理（query_encyclopedia 支持多结果）
            return {"match": True, "attribute": "精灵查询", "data": text}

        # --- 无精确匹配 → 模糊匹配到就发服务器+提示 ---
        suggestion = None
        suggested = None
        # 拆字匹配
        for ch in text:
            for n in self.spirit_names:
                if ch in n:
                    suggestion = f"猜你想找：是不是【{self.spirits[n]['display_name']}】？\n\n无需全字段匹配，支持模糊搜索"
                    suggested = n
                    break
            if suggested:
                break
        # 拼音匹配（查表）
        if not suggested:
            input_py = self._input_to_pinyin(text)
            for n in self.spirit_names:
                info = self.spirits.get(n, {})
                name_py = info.get("name_pinyin", "")
                if name_py and (input_py == name_py or input_py in name_py or name_py in input_py):
                    suggestion = f"猜你想找：是不是【{info['display_name']}】？\n\n无需全字段匹配，支持模糊搜索"
                    suggested = n
                    break
        if suggested:
            return {"match": True, "attribute": "精灵查询", "data": suggested, "suggestion": suggestion}

        return {"match": False, "suggestion": f"未找到相关内容: {text}"}

    # ---------- 消息处理 ----------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        msg = event.message_str.strip()
        trigger = self.config.get("trigger_word", "查询 ")

        query_text = ""
        if msg.startswith(trigger):
            query_text = msg[len(trigger):].strip()
        else:
            self_id = str(event.get_self_id())
            if self_id and self_id in msg:
                clean = _re.sub(r'\[CQ:at,qq=\d+\]', '', msg).strip()
                if clean:
                    query_text = clean

        if not query_text:
            logger.info(f"消息未触发查询: msg={repr(msg[:50])} trigger={repr(trigger)} self_id={event.get_self_id()}")
            return

        result = self._try_match(query_text)
        logger.info(f"查询: [{result.get('attribute','?')}] {query_text} -> match={result['match']}")

        # 未匹配 → 本地直接回复
        if not result["match"]:
            yield event.plain_result(result.get("suggestion", "未匹配"))
            return

        # 有模糊提示 → 先发提示文字
        suggestion = result.get("suggestion", "")
        if suggestion:
            yield event.plain_result(suggestion)

        # 匹配 → 发送到计算服务
        resp_text = await self._call_api(result["attribute"], result["data"])

        # 渲染图片
        title_map = {
            "精灵查询": "✦ 精灵查询",
            "蛋组查询": "✦ 蛋组查询",
            "孵蛋预测": "✦ 孵蛋预测",
        }
        if self.enable_render_image:
            img_url = await self._render_as_image(
                resp_text,
                title_map.get(result["attribute"], "✦ 查询结果"),
                user_id=str(event.get_sender_id()),
                group_id=str(event.get_group_id()),
            )
            if img_url:
                yield event.image_result(img_url)
            else:
                yield event.plain_result(resp_text)
        else:
            yield event.plain_result(resp_text)

    # ---------- 网络/渲染 ----------

    async def _call_api(self, attribute: str, data: str) -> str:
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
                payload = {"attribute": attribute, "data": data}
                async with session.post(self.api_url, json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("result", "查询无结果")
                    return f"计算服务返回异常: HTTP {resp.status}"
        except Exception as e:
            logger.error(f"计算服务调用失败: {e}")
            return f"计算服务调用失败: {e}"

    async def _render_as_image(self, text: str, title: str = "",
                                user_id: str = "", group_id: str = "") -> str:
        if not text:
            return ""
        try:
            import sys as _sys
            import datetime as _dt
            _sys.path.insert(0, str(_PLUGIN_DIR))
            from image_renderer import render_text_to_image
            lines = text.split("\n")
            query_info = {
                "time": _dt.datetime.now().strftime("%m-%d %H:%M"),
                "group": f"\u7fa4 {group_id}" if group_id else "\u79c1\u804a",
                "url": "github.com/774417678/astrbot_plugin_rocopetconfirm_cinene",
                "user": f"\u67e5\u8be2\u4eba {user_id}",
            }
            img_path = await asyncio.to_thread(
                render_text_to_image, title, lines,
                query_info=query_info
            )
            return img_path
        except Exception as e:
            logger.error(f"\u56fe\u7247\u6e32\u67d3\u5931\u8d25: {e}")
            return ""


    async def terminate(self):
        logger.info("插件已卸载")
