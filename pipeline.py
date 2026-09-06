# -*- coding: utf-8 -*-
"""通用阶段流水线引擎：多阶段长任务的状态机 + 检查点恢复 + 质量债策略。

设计（自研方案，参照 LangGraph 的 state/checkpoint 思想，零依赖）：
- 每个阶段是纯函数 fn(state, ctx) -> dict，返回值合并进流水线 state；
- 阶段失败分两级：fail="debt" 记质量债继续跑（局部问题不放大为全局失败），
  fail="stop" 立即停链（结构级失败）；
- 全量状态落 JSON（CONFIG_DIR/pipelines/<pid>.json，临时文件 + os.replace
  原子替换），每个阶段结束即落盘，中断后 restore 即可从断点恢复；
- 阶段内部可循环（如逐章生成）时用 ctx.save_state 做中间落盘、用
  ctx.is_stopped / ctx.pause 协作式暂停——恢复时阶段自己跳过已完成部分；
- on_stop 协作式停止：每个阶段开始前检查。
"""

from __future__ import annotations

import json
import os
import time

import config


class StageStopError(Exception):
    """结构级失败：终止整条流水线。"""


class StageDebtError(Exception):
    """局部失败：记为质量债，流水线继续。"""


class StagePaused(Exception):
    """阶段内部请求暂停（如逐章循环中用户停止）。"""


class Stage:
    """流水线阶段：名称 + 执行函数 + 失败分级策略。"""

    def __init__(self, name: str, fn, fail: str = "debt"):
        self.name = name
        self.fn = fn
        self.fail = fail              # "debt" | "stop"


class StageCtx:
    """传给阶段函数的上下文：事件上报 / 中间落盘 / 暂停协作。"""

    def __init__(self, pipeline, on_event):
        self.pipeline = pipeline
        self._on_event = on_event

    def emit(self, ev_type: str, **kw):
        """向 UI 转发阶段内事件（chapter_done 等）。"""
        self._on_event({"type": ev_type, "stage": self.pipeline.cursor, **kw})

    def save_state(self, updates: dict):
        """阶段中间落盘：合并进 state 并立即持久化（供断点恢复）。"""
        self.pipeline.state.update(updates or {})
        self.pipeline.updated = time.time()
        self.pipeline.save()

    def is_stopped(self) -> bool:
        return self.pipeline.stop_requested

    def pause(self):
        """阶段内部主动暂停（恢复时重跑本阶段，需自行跳过已完成部分）。"""
        raise StagePaused()


class Pipeline:
    """阶段流水线：状态、进度、质量债、检查点。"""

    def __init__(self, pid: str, title: str, stages: list, state: dict | None = None):
        self.pid = pid
        self.title = title
        self.stages = stages
        self.state = state or {}
        self.status: dict[str, str] = {s.name: "pending" for s in stages}
        self.debts: list[dict] = []
        self.cursor: str | None = stages[0].name if stages else None
        self.pipeline_status = "pending"   # pending/running/paused/done/failed
        self.error = ""
        self.stop_requested = False
        self.updated = time.time()

    # ---------------- 执行 ----------------

    def run(self, on_event=None, on_stop=None, until: str | None = None) -> str:
        """从 cursor 起跑完剩余阶段；until=阶段名时跑完该阶段即暂停。

        返回终态 running/paused/done/failed。"""
        on_event = on_event or (lambda e: None)
        on_stop = on_stop or (lambda: False)
        self.stop_requested = False
        self.pipeline_status = "running"
        self.save()
        on_event({"type": "pipeline_started", "pid": self.pid, "title": self.title})
        idx = self._stage_index(self.cursor)
        while idx is not None and idx < len(self.stages):
            stage = self.stages[idx]
            if self.stop_requested or on_stop():
                return self._pause(on_event)
            self.status[stage.name] = "running"
            self.save()
            on_event({"type": "stage_start", "name": stage.name})
            ctx = StageCtx(self, on_event)
            try:
                updates = stage.fn(self.state, ctx) or {}
                self.state.update(updates)
                self.status[stage.name] = "done"
            except StagePaused:
                self.status[stage.name] = "pending"
                return self._pause(on_event)
            except StageStopError as e:
                self.status[stage.name] = "failed"
                return self._fail(str(e) or stage.name, on_event)
            except StageDebtError as e:
                self.status[stage.name] = "debt"
                self._record_debt(stage, str(e), on_event)
            except Exception as e:        # noqa: BLE001  未分类异常按阶段策略分级
                if stage.fail == "stop":
                    self.status[stage.name] = "failed"
                    return self._fail(str(e), on_event)
                self.status[stage.name] = "debt"
                self._record_debt(stage, str(e), on_event)
            self.updated = time.time()
            idx += 1
            self.cursor = self.stages[idx].name if idx < len(self.stages) else None
            self.save()
            on_event({"type": "stage_done", "name": stage.name})
            if until and stage.name == until:   # 逐阶段确认模式：跑完即停
                self.pipeline_status = "paused"
                self.save()
                on_event({"type": "pipeline_paused", "pid": self.pid})
                return "paused"
        self.pipeline_status = "done"
        self.save()
        on_event({"type": "pipeline_done", "pid": self.pid})
        return "done"

    def _pause(self, on_event) -> str:
        self.pipeline_status = "paused"
        self.updated = time.time()
        self.save()
        on_event({"type": "pipeline_paused", "pid": self.pid})
        return "paused"

    def _fail(self, detail: str, on_event) -> str:
        self.pipeline_status = "failed"
        self.error = detail
        self.updated = time.time()
        self.save()
        on_event({"type": "pipeline_failed", "pid": self.pid, "detail": detail})
        return "failed"

    def _record_debt(self, stage, detail: str, on_event):
        self.debts.append({"stage": stage.name, "detail": detail,
                           "time": time.strftime("%Y-%m-%d %H:%M:%S")})
        on_event({"type": "stage_debt", "name": stage.name, "detail": detail})

    def _stage_index(self, name: str | None) -> int | None:
        if name is None:
            return None
        for i, s in enumerate(self.stages):
            if s.name == name:
                return i
        return 0                       # 未知游标（阶段定义变更）→ 从头重跑

    def request_stop(self):
        self.stop_requested = True

    # ---------------- 持久化 ----------------

    def to_dict(self) -> dict:
        return {"pid": self.pid, "title": self.title,
                "state": self.state, "status": self.status,
                "debts": self.debts, "cursor": self.cursor,
                "pipeline_status": self.pipeline_status,
                "error": self.error, "updated": self.updated}

    def save(self):
        try:
            d = _root()
            os.makedirs(d, exist_ok=True)
            tmp = os.path.join(d, self.pid + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)
            os.replace(tmp, _path(self.pid))
        except OSError:
            pass                       # 落盘失败不阻断执行（下个阶段再试）

    @classmethod
    def restore(cls, data: dict, stages: list) -> "Pipeline":
        """从落盘数据重建；stages 由代码侧重新提供（状态不含可执行体）。"""
        p = cls(data["pid"], data.get("title", ""), stages,
                data.get("state") or {})
        p.status = data.get("status") or p.status
        p.debts = data.get("debts") or []
        p.cursor = data.get("cursor")
        p.pipeline_status = data.get("pipeline_status", "pending")
        p.error = data.get("error", "")
        p.updated = data.get("updated", 0.0)
        for s in stages:               # 阶段定义新增的 → 补 pending
            p.status.setdefault(s.name, "pending")
        if p.pipeline_status == "running":   # 进程中断时正在跑 → 回退待恢复
            p.pipeline_status = "paused"
        return p


def _root() -> str:
    return os.path.join(config.CONFIG_DIR, "pipelines")


def _path(pid: str) -> str:
    return os.path.join(_root(), pid + ".json")


def load(pid: str, stages: list) -> Pipeline | None:
    """按 pid 恢复流水线；不存在/损坏返回 None。"""
    try:
        with open(_path(pid), encoding="utf-8") as f:
            return Pipeline.restore(json.load(f), stages)
    except Exception:                  # noqa: BLE001
        return None


def list_pipelines() -> list[dict]:
    """全部流水线摘要（按更新时间新→旧）。"""
    out = []
    try:
        names = os.listdir(_root())
    except OSError:
        return []
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(_root(), name), encoding="utf-8") as f:
                d = json.load(f)
            out.append({"pid": d.get("pid"), "title": d.get("title", ""),
                        "pipeline_status": d.get("pipeline_status"),
                        "cursor": d.get("cursor"),
                        "debts": len(d.get("debts") or []),
                        "updated": d.get("updated", 0)})
        except Exception:              # noqa: BLE001  损坏文件跳过
            continue
    out.sort(key=lambda x: -x["updated"])
    return out
