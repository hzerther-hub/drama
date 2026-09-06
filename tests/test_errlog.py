# -*- coding: utf-8 -*-
"""errlog：异常上报（日志文件 + 通知回调）单元测试。"""

import threading

import errlog


def test_report_writes_log_and_notifies(tmp_path, monkeypatch):
    notified = []
    r = errlog.ErrorReporter(str(tmp_path), notify=notified.append)
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        n = r.report("tk-callback", *sys.exc_info())
    assert n == 1
    text = (tmp_path / "ui_errors.log").read_text(encoding="utf-8")
    assert "ValueError: boom" in text
    assert "(tk-callback)" in text
    assert notified and "ui_errors.log" in notified[0]
    assert r.count == 1


def test_report_survives_unwritable_dir(tmp_path, monkeypatch):
    # 目录不可建（指向一个文件路径充当目录）→ 只计数、不抛
    blocked = tmp_path / "notadir"
    blocked.write_text("x", encoding="utf-8")
    r = errlog.ErrorReporter(str(blocked), notify=lambda _m: None)
    try:
        raise RuntimeError("x")
    except RuntimeError:
        import sys
        n = r.report("thread", *sys.exc_info())
    assert n == 1 and r.path == ""


def test_log_rotation(tmp_path, monkeypatch):
    monkeypatch.setattr(errlog, "_MAX_LOG_BYTES", 10)
    r = errlog.ErrorReporter(str(tmp_path))
    for i in range(3):
        r.report("tk-callback", ValueError, ValueError(f"e{i}"), None)
    assert (tmp_path / "ui_errors.log.old").exists()


def test_install_tk_and_threading(tmp_path):
    r = errlog.ErrorReporter(str(tmp_path))

    class FakeRoot:
        pass
    fake = FakeRoot()
    r.install_tk(fake)
    assert callable(fake.report_callback_exception)
    fake.report_callback_exception(ValueError, ValueError("gui"), None)

    old = threading.excepthook
    r.install_threading()
    try:
        threading.excepthook(threading.ExceptHookArgs(
            (ValueError, ValueError("worker"), None, None)))
    finally:
        threading.excepthook = old

    text = (tmp_path / "ui_errors.log").read_text(encoding="utf-8")
    assert "ValueError: gui" in text and "(tk-callback)" in text
    assert "ValueError: worker" in text and "(thread)" in text
    assert r.count == 2
