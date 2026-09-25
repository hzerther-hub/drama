# -*- coding: utf-8 -*-
"""通用阶段流水线引擎：多阶段长任务的状态机 + 检查点恢复 + 质量债策略。

设计（自研方案，参照 LangGraph 的 state/checkpoint 思想，零依赖）：
- 每个阶段是纯函数 fn(state, ctx) -> dict，返回值合并进流水线 state；
- 阶段失败分两级：fail="debt" 记质量债继续跑（局部问题不放大为全局失败），
  fail="stop" 立即停链（结构级失败）；
- 全量状态落 JSON（优先 `<书稿目录>/pipelines/<pid>.json`，书未建目录或目录
  被删时回落 `CONFIG_DIR/pipelines/<pid>.json`；临时文件 + os.replace 原子替换），
  每个阶段结束即落盘，中断后 restore 即可从断点恢复；
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
        self._title = title          # 建管线时的灵感截断，仅作兜底
        self.stages = stages
        self.state = state or {}
        self.status: dict[str, str] = {s.name: "pending" for s in stages}
        self.debts: list[dict] = []
        self.cursor: str | None = stages[0].name if stages else None
        self.pipeline_status = "pending"   # pending/running/paused/done/failed
        self.error = ""
        self.stop_requested = False
        self.updated = time.time()
        # 检查点健康信号：落盘失败次数与最近一次原因。断点恢复的根基，
        # 静默吞掉会让「已保存」成为假象，故随状态一起持久化供排查。
        self.save_errors = 0
        self.save_error = ""

    @property
    def title(self) -> str:
        """书名：优先 state.title（setup 阶段定的正式书名），
        否则退回建管线时的灵感截断。"""
        return (self.state or {}).get("title") or self._title

    @title.setter
    def title(self, v: str):
        self._title = v or ""

    # ---------------- 执行 ----------------

    def run(self, on_event=None, on_stop=None, until: str | None = None) -> str:
        """从 cursor 起跑完剩余阶段；until=阶段名时跑完该阶段即暂停。

        返回终态 running/paused/done/failed。"""
        on_event = self._make_sink(on_event)
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

    def _make_sink(self, on_event):
        """包装事件回调：转发 UI 之外，append-only 写入事件溯源日志。"""
        def sink(e):
            try:
                on_event(e)
            except Exception:          # noqa: BLE001  UI 异常不阻断流水线
                pass
            self._log_event(e)
        return sink

    def _log_event(self, e: dict):
        """SSOT-lite：append-only 事件日志（书目录 pipelines/ 内，旧档回落
        CONFIG_DIR/pipelines/）。"""
        try:
            d = _book_pipeline_dir(self.state) or _root()
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, self.pid + ".events.jsonl"), "a",
                      encoding="utf-8") as f:
                f.write(json.dumps({"t": time.time(), **e},
                                   ensure_ascii=False) + "\n")
        except OSError:
            pass
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
                "error": self.error, "updated": self.updated,
                "save_errors": self.save_errors,
                "save_error": self.save_error}

    def save(self):
        try:
            book_d = _book_pipeline_dir(self.state)
            d = book_d or _root()
            os.makedirs(d, exist_ok=True)
            tmp = os.path.join(d, self.pid + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)
            os.replace(tmp, os.path.join(d, self.pid + ".json"))
            if book_d:
                # 单档约束：书目录的 pipelines/ 只挂当前这条（用户约定：
                # novels 只有一个书目录、目录下只有一个 pipelines、%APPDATA%
                # 不留存档），其他 pid 的旧档直接删除
                _evict_others(book_d, self.pid)
                self._remove_legacy()
        except Exception as e:         # noqa: BLE001  落盘失败不阻断执行（下个阶段再试）
            # 记录健康信号：断点恢复依赖落盘，静默失败必须可查。
            # 下次 save 成功时会连同计数一起持久化。
            self.save_errors += 1
            self.save_error = f"{type(e).__name__}: {e}"[:200]

    def _remove_legacy(self):
        """状态已迁入书目录后删除 CONFIG_DIR 同名旧档（不存在则忽略）。"""
        try:
            legacy = _path(self.pid)
            if os.path.isfile(legacy):
                os.remove(legacy)
        except OSError:
            pass

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
        p.save_errors = int(data.get("save_errors", 0) or 0)
        p.save_error = data.get("save_error", "") or ""
        for s in stages:               # 阶段定义新增的 → 补 pending
            p.status.setdefault(s.name, "pending")
        if p.pipeline_status == "running":   # 进程中断时正在跑 → 回退待恢复
            p.pipeline_status = "paused"
        # 旧书没存 drama_style：补齐默认，让后续资产生成/工作台无空值
        if "drama_style" not in p.state or not p.state["drama_style"]:
            try:
                import dramavideo as _dv
                p.state["drama_style"] = _dv.resolve_style(p.state)
            except Exception:          # noqa: BLE001
                pass
        return p


def _root() -> str:
    """兼容落点：CONFIG_DIR/pipelines（未建书目录的书、旧档、测试打桩点）。"""
    return os.path.join(config.CONFIG_DIR, "pipelines")


def _path(pid: str) -> str:
    return os.path.join(_root(), pid + ".json")


_DIR_NAME = "pipelines"                # 书稿目录内的流水线子目录名


def _books_root() -> str:
    """书稿根（novels/）：委托 novel_chain 推导（函数内导入避免循环依赖）。"""
    import novel_chain
    return novel_chain._novels_root()


def _book_pipeline_dir(state: dict | None) -> str | None:
    """书目录内的流水线目录；无书目录或书目录已被删除时返回 None。"""
    d = (state or {}).get("dir")
    if not d:
        return None
    # 书目录被用户删掉时不复活它（makedirs 会重建整棵书目录）：回落旧位置
    if not os.path.isdir(d):
        return None
    return os.path.join(d, _DIR_NAME)


def _archive_move(src: str, dst_dir: str, name: str):
    """把文件挪进 CONFIG_DIR 存档区（可能跨盘：写 tmp + replace + 删源）。"""
    dst = os.path.join(dst_dir, name)
    tmp = dst + ".tmp"
    with open(src, encoding="utf-8") as f, open(tmp, "w",
                                                encoding="utf-8") as g:
        g.write(f.read())
    os.replace(tmp, dst)
    os.remove(src)


def _evict_others(book_pipelines_dir: str, keep_pid: str):
    """单档约束：书目录 pipelines/ 只保留 keep_pid 一条，其他 pid 的档案
    （含事件日志）直接删除——按用户约定 %APPDATA% 不留存档，书目录外
    不应有旧档案残留。""" 
    try:
        names = os.listdir(book_pipelines_dir)
    except OSError:
        return
    for name in names:
        pid = name[:-5] if name.endswith(".json") else ""
        if not pid or pid == keep_pid:
            continue
        try:
            os.remove(os.path.join(book_pipelines_dir, name))
            ev = os.path.join(book_pipelines_dir, pid + ".events.jsonl")
            if os.path.isfile(ev):
                os.remove(ev)
        except OSError:
            continue


def _migrate_legacy_all():
    """把 CONFIG_DIR 旧档批量迁进各自书目录（幂等，list_pipelines 时触发）。

    只迁 state.dir 在磁盘上真实存在的书；书目录 pipelines/ 已被别的 pid
    占用时跳过（单档约束：迁入会和占位档打架，等该书下次 save 自然换防）；
    书目录内已有同名档时保留 updated 较新的那份。
    """
    try:
        names = os.listdir(_root())
    except OSError:
        return
    for name in names:
        if not name.endswith(".json"):
            continue
        src = os.path.join(_root(), name)
        try:
            with open(src, encoding="utf-8") as f:
                jd = json.load(f)
            d = _book_pipeline_dir(jd.get("state"))
            if not d:
                continue
            occupied = any(n.endswith(".json") and n != name
                           for n in os.listdir(d)) if os.path.isdir(d) else False
            if occupied:
                continue               # 目录挂着别的 pid：单档约束，不迁入
            os.makedirs(d, exist_ok=True)
            if os.path.isfile(os.path.join(d, name)):
                with open(os.path.join(d, name), encoding="utf-8") as f:
                    cur = json.load(f)
                if float(jd.get("updated", 0) or 0) <= float(
                        cur.get("updated", 0) or 0):
                    os.remove(src)     # 书目录那份更新：旧档直接丢弃
                    continue
            _archive_move(src, d, name)
        except Exception:              # noqa: BLE001  单档迁移失败不影响其余
            continue


def _find_in_books(pid: str) -> str | None:
    """在各书的 pipelines/ 子目录里找 <pid>.json；找不到返回 None。"""
    try:
        root = _books_root()
        names = os.listdir(root)
    except Exception:                  # noqa: BLE001  无书稿根/不可读 → 当作没有
        return None
    for name in names:
        cand = os.path.join(root, name, _DIR_NAME, pid + ".json")
        if os.path.isfile(cand):
            return cand
    return None


def load(pid: str, stages: list) -> Pipeline | None:
    """按 pid 恢复流水线：先查 CONFIG_DIR（旧档/未建书），再扫各书目录。"""
    for path in (_path(pid), _find_in_books(pid)):
        if not path:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                return Pipeline.restore(json.load(f), stages)
        except Exception:              # noqa: BLE001
            continue
    return None


def delete_record(pid: str) -> bool:
    """删除一条流水线档案（状态 json + 事件日志；CONFIG_DIR 或书目录均可）。
    只删档案，不动书稿目录与正文。返回是否删到了状态 json。"""
    removed = False
    for path in (_path(pid), _find_in_books(pid)):
        if path and os.path.isfile(path):
            try:
                os.remove(path)
                removed = True
            except OSError:
                pass
    ev = pid + ".events.jsonl"
    for d in (_root(), os.path.dirname(_find_in_books(pid) or "")):
        p = os.path.join(d, ev) if d else ""
        if p and os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass
    return removed


def list_pipelines() -> list[dict]:
    """全部流水线摘要（按更新时间新→旧）：CONFIG_DIR 旧档 + 各书目录新档，
    同 pid 双份并存时保留 updated 较新的一份。"""
    _migrate_legacy_all()
    by_pid: dict = {}
    dirs = [_root()]
    try:
        root = _books_root()
        dirs += [os.path.join(root, n, _DIR_NAME)
                 for n in os.listdir(root)
                 if os.path.isdir(os.path.join(root, n, _DIR_NAME))]
    except Exception:                  # noqa: BLE001
        pass
    for d in dirs:
        loc = "book" if d != _root() else "cfg"
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in names:
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(d, name), encoding="utf-8") as f:
                    jd = json.load(f)
                row = {"pid": jd.get("pid"),
                       # 书名优先取 state.title（正式书名）；顶层 title 是
                       # 建管线时的灵感截断，多行粘贴时会是一段正文开头
                       "title": ((jd.get("state") or {}).get("title")
                                 or jd.get("title", "")),
                       "pipeline_status": jd.get("pipeline_status"),
                       "cursor": jd.get("cursor"),
                       "debts": len(jd.get("debts") or []),
                       "save_errors": int(jd.get("save_errors", 0) or 0),
                       "updated": jd.get("updated", 0),
                       "loc": loc}
            except Exception:          # noqa: BLE001  损坏文件跳过
                continue
            pid = row["pid"] or name[:-5]
            old = by_pid.get(pid)
            if old is None or row["updated"] >= old["updated"]:
                by_pid[pid] = row
    return sorted(by_pid.values(), key=lambda x: -x["updated"])
