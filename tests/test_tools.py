# -*- coding: utf-8 -*-
"""tools.py：8 个内置工具的执行器 + 权限分类。"""

import os
import sys

import pytest

import tools


@pytest.fixture(autouse=True)
def workspace(tmp_path):
    """每个用例都在独立的临时工作目录里执行。"""
    old = tools.get_workspace()
    tools.set_workspace(str(tmp_path))
    yield str(tmp_path)
    tools.set_workspace(old)


class TestReadFile:
    def test_line_numbers(self, workspace):
        with open(os.path.join(workspace, "a.txt"), "w", encoding="utf-8") as f:
            f.write("第一行\n第二行")
        out = tools.execute_tool("read_file", {"path": "a.txt"})
        assert "1 | 第一行" in out
        assert "2 | 第二行" in out

    def test_relative_path_resolves_to_workspace(self, workspace):
        with open(os.path.join(workspace, "b.txt"), "w", encoding="utf-8") as f:
            f.write("x")
        assert "x" in tools.execute_tool("read_file", {"path": "b.txt"})

    def test_missing_file_returns_error(self):
        out = tools.execute_tool("read_file", {"path": "no-such-file.xyz"})
        assert "错误" in out and "不存在" in out

    def test_directory_returns_error(self, workspace):
        out = tools.execute_tool("read_file", {"path": "."})
        assert "错误" in out

    def test_empty_file(self, workspace):
        open(os.path.join(workspace, "empty.txt"), "w").close()
        assert tools.execute_tool("read_file", {"path": "empty.txt"}) == "(空文件)"


class TestWriteFile:
    def test_write_and_read_back(self, workspace):
        out = tools.execute_tool("write_file",
                                 {"path": "sub/dir/c.txt", "content": "内容"})
        assert "已写入" in out
        with open(os.path.join(workspace, "sub", "dir", "c.txt"),
                  encoding="utf-8") as f:
            assert f.read() == "内容"

    def test_bare_filename_no_makedirs_crash(self, workspace):
        out = tools.execute_tool("write_file",
                                 {"path": "bare.txt", "content": "y"})
        assert "已写入" in out


class TestListDir:
    def test_marks_directories(self, workspace):
        os.makedirs(os.path.join(workspace, "subdir"))
        open(os.path.join(workspace, "f.txt"), "w").close()
        out = tools.execute_tool("list_dir", {"path": "."})
        assert "subdir/" in out
        assert "f.txt" in out

    def test_missing_dir(self):
        assert "错误" in tools.execute_tool("list_dir", {"path": "nope/"})

    def test_empty_dir(self, workspace):
        assert tools.execute_tool("list_dir", {"path": "."}) == "(空目录)"


class TestGlobSearch:
    def test_pattern(self, workspace):
        open(os.path.join(workspace, "x.py"), "w").close()
        open(os.path.join(workspace, "y.md"), "w").close()
        out = tools.execute_tool("glob_search", {"pattern": "*.py"})
        assert "x.py" in out and "y.md" not in out

    def test_no_match(self, workspace):
        assert "未找到" in tools.execute_tool("glob_search",
                                              {"pattern": "*.nonexistent"})


class TestGrepSearch:
    def test_regex_hit_with_line_number(self, workspace):
        with open(os.path.join(workspace, "g.py"), "w", encoding="utf-8") as f:
            f.write("def foo():\n    return 42\n")
        out = tools.execute_tool("grep_search",
                                 {"pattern": "return \\d+", "path": "."})
        assert "g.py:2:" in out

    def test_invalid_regex_falls_back_to_literal(self, workspace):
        with open(os.path.join(workspace, "h.txt"), "w", encoding="utf-8") as f:
            f.write("price is ((5))\n")
        out = tools.execute_tool("grep_search",
                                 {"pattern": "((5))", "path": "."})
        assert "h.txt:1:" in out

    def test_skips_hidden_dirs(self, workspace):
        hidden = os.path.join(workspace, ".hidden")
        os.makedirs(hidden)
        with open(os.path.join(hidden, "s.txt"), "w", encoding="utf-8") as f:
            f.write("secret-keyword\n")
        out = tools.execute_tool("grep_search",
                                 {"pattern": "secret-keyword", "path": "."})
        assert "未找到" in out

    def test_no_match(self, workspace):
        assert "未找到" in tools.execute_tool(
            "grep_search", {"pattern": "zzz-absent", "path": "."})


class TestRunShell:
    # 用各平台 shell 内建命令，避免依赖外部可执行文件
    if sys.platform == "win32":
        _ECHO = "echo 42"
        _EXIT3 = "exit 3"
        _STDERR = "echo oops 1>&2"
    else:
        _ECHO = "echo 42"
        _EXIT3 = "exit 3"
        _STDERR = "echo oops >&2"

    def test_stdout(self, workspace):
        out = tools.execute_tool("run_shell", {"command": self._ECHO})
        assert "42" in out

    def test_nonzero_exit_code_reported(self, workspace):
        out = tools.execute_tool("run_shell", {"command": self._EXIT3})
        assert "退出码 3" in out

    def test_stderr_captured(self, workspace):
        out = tools.execute_tool("run_shell", {"command": self._STDERR})
        assert "[stderr]" in out and "oops" in out


class TestPermissions:
    def test_write_tools_set(self):
        assert tools.is_write_tool("write_file")
        assert tools.is_write_tool("run_shell")
        assert not tools.is_write_tool("read_file")

    def test_readonly_schemas_exclude_writes(self):
        names = {s["function"]["name"] for s in tools.readonly_schemas()}
        assert "write_file" not in names
        assert "run_shell" not in names
        assert "read_file" in names

    def test_unknown_tool_returns_error(self):
        assert "未知工具" in tools.execute_tool("not_a_tool", {})


class TestDescribeArguments:
    def test_run_shell_passthrough(self):
        assert tools.describe_arguments("run_shell",
                                        {"command": "ls"}) == "ls"

    def test_write_file_truncates_long_content(self):
        out = tools.describe_arguments(
            "write_file", {"path": "a.txt", "content": "x" * 500})
        assert "截断" in out and len(out) < 500


class TestWebSearchParsers:
    """离线解析器测试：不联网，直接喂 HTML 片段。"""

    def test_strip_tags_and_entities(self):
        assert tools._strip_tags("<b>Tom &amp; Jerry</b>") == "Tom & Jerry"

    def test_parse_duckduckgo_uddg_unquote(self):
        html = ('<a class="result__a" href="//duckduckgo.com/l/?uddg='
                'https%3A%2F%2Fexample.com%2Fp">标题</a>'
                '<a class="result__snippet">摘要</a>')
        results = tools._parse_duckduckgo(html)
        assert results == [("标题", "https://example.com/p", "摘要")]

    def test_parse_bing(self):
        html = ('<li class="b_algo"><h2><a href="https://a.example">T</a></h2>'
                '<p>S</p></li>')
        assert tools._parse_bing(html) == [("T", "https://a.example", "S")]


class TestSandbox:
    """写操作沙箱：write_file 限工作区内，run_shell 拦高危命令。"""

    def test_write_inside_workspace_allowed(self, workspace):
        out = tools.execute_tool("write_file",
                                 {"path": "ok.txt", "content": "v"})
        assert "已写入" in out

    def test_write_outside_workspace_blocked(self, workspace, tmp_path):
        outside = str(tmp_path.parent / "outside-evil.txt")
        out = tools.execute_tool("write_file",
                                 {"path": outside, "content": "v"})
        assert "沙箱" in out and "错误" in out
        assert not os.path.exists(outside)

    def test_write_outside_allowed_when_sandbox_off(self, monkeypatch,
                                                    workspace, tmp_path):
        monkeypatch.setattr(tools.config, "SANDBOX", False)
        outside = str(tmp_path.parent / "outside-ok.txt")
        try:
            out = tools.execute_tool("write_file",
                                     {"path": outside, "content": "v"})
            assert "已写入" in out
        finally:
            if os.path.exists(outside):
                os.remove(outside)

    def test_path_in_workspace_normalizes(self, workspace):
        assert tools.path_in_workspace(os.path.join(workspace, "a", "..", "b"))
        assert not tools.path_in_workspace(os.path.join(workspace, "..", "x"))

    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "rm -rf /*",
        "sudo mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda bs=1M",
        ":(){ :|:& };:",
        "shutdown /s /t 0",
        "reboot",
        "format C: /y",
        "rd /s /q C:\\",
    ])
    def test_dangerous_commands_blocked(self, workspace, cmd):
        out = tools.execute_tool("run_shell", {"command": cmd})
        assert "沙箱拦截" in out, cmd

    @pytest.mark.parametrize("cmd", [
        "git status",
        "rm -rf ./build",            # 删工作区内的构建目录是正常开发操作
        "python setup.py install",
        "ls -la /tmp",
    ])
    def test_normal_commands_not_blocked(self, workspace, cmd):
        assert tools.shell_command_blocked(cmd) is None

    def test_dangerous_allowed_when_sandbox_off(self, monkeypatch, workspace):
        monkeypatch.setattr(tools.config, "SANDBOX", False)
        # 沙箱关掉后拦截不再生效（命令本身可能失败，但不应是沙箱错误）
        out = tools.execute_tool("run_shell", {"command": "echo ok"})
        assert "沙箱" not in out


class TestWorkspaceIsolation:
    """push_workspace：临时切换工作目录，退出自动恢复。"""

    def test_push_workspace_restores(self, tmp_path):
        old = tools.get_workspace()
        with tools.push_workspace(str(tmp_path)) as ws:
            assert tools.get_workspace() == str(tmp_path) == ws
        assert tools.get_workspace() == old

    def test_push_workspace_restores_on_exception(self, tmp_path):
        old = tools.get_workspace()
        with pytest.raises(RuntimeError):
            with tools.push_workspace(str(tmp_path)):
                raise RuntimeError("boom")
        assert tools.get_workspace() == old


class TestBadArgumentsDegrade:
    """模型传坏参数（null/缺失）时：返回错误文本并附「继续」提示，不抛异常。"""

    def test_run_shell_null_command(self):
        out = tools.execute_tool("run_shell", {"command": None})
        assert out.startswith("错误：") and "继续" in out

    def test_run_shell_missing_command(self):
        out = tools.execute_tool("run_shell", {})
        assert out.startswith("错误：")

    def test_describe_arguments_never_returns_none(self):
        assert tools.describe_arguments("run_shell", {"command": None}) == ""
        assert tools.describe_arguments("write_file", {"path": None,
                                                       "content": None}) == \
            "文件: \n\n"
        # 正常路径不受影响
        assert tools.describe_arguments("run_shell", {"command": "ls"}) == "ls"

    def test_execute_tool_exception_returns_hint(self, workspace):
        # read_file 的 path 为 null → _resolve 抛异常 → 包装成带提示的错误文本
        out = tools.execute_tool("read_file", {"path": None})
        assert out.startswith("错误：")
        assert "继续完成当前任务" in out
        assert "不要因此停止" in out
class TestGitBranch:
    def test_non_repo_returns_none(self, workspace):
        assert tools.git_branch(workspace) is None

    def test_reads_branch_from_head(self, workspace):
        git = os.path.join(workspace, ".git")
        os.makedirs(git)
        with open(os.path.join(git, "HEAD"), "w", encoding="utf-8") as f:
            f.write("ref: refs/heads/dev\n")
        assert tools.git_branch(workspace) == "dev"

    def test_nested_feature_branch(self, workspace):
        git = os.path.join(workspace, ".git")
        os.makedirs(git)
        with open(os.path.join(git, "HEAD"), "w", encoding="utf-8") as f:
            f.write("ref: refs/heads/feature/foo\n")
        assert tools.git_branch(workspace) == "feature/foo"

    def test_walks_up_to_parent_repo(self, workspace):
        git = os.path.join(workspace, ".git")
        os.makedirs(git)
        with open(os.path.join(git, "HEAD"), "w", encoding="utf-8") as f:
            f.write("ref: refs/heads/master\n")
        sub = os.path.join(workspace, "src", "pkg")
        os.makedirs(sub)
        assert tools.git_branch(sub) == "master"

    def test_detached_head_short_hash(self, workspace):
        git = os.path.join(workspace, ".git")
        os.makedirs(git)
        with open(os.path.join(git, "HEAD"), "w", encoding="utf-8") as f:
            f.write("abcdef1234567890\n")
        assert tools.git_branch(workspace) == "abcdef1"

    def test_worktree_gitdir_file(self, workspace, tmp_path):
        real_git = tmp_path / "real.git"
        real_git.mkdir()
        (real_git / "HEAD").write_text("ref: refs/heads/wt-branch\n",
                                       encoding="utf-8")
        with open(os.path.join(workspace, ".git"), "w", encoding="utf-8") as f:
            f.write(f"gitdir: {real_git}\n")
        assert tools.git_branch(workspace) == "wt-branch"
