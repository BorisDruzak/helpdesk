import pytest

import _thread
import ctypes
import io
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from scripts.owned_child_process import run_child
import scripts.owned_child_process as owned_child_process

from scripts.run_with_local_postgres import child_environment, redact, validate_cluster_path


def test_child_environment_replaces_external_database_and_disables_shared_fallback():
    env = child_environment({
        "DATABASE_URL": "postgresql+asyncpg://external/production",
        "TEST_DATABASE_URL": "postgresql+asyncpg://external/production",
        "PC_CLIENT_ALLOW_SHARED_TEST_DB": "1",
        "PC_CLIENT_TEST_DB_TEMPLATE": "1",
        "PC_CLIENT_KEEP_TEST_DB": "1",
    }, "postgresql+asyncpg://test_admin:generated@127.0.0.1:54321/postgres")

    assert env["TEST_DATABASE_ADMIN_URL"].endswith("@127.0.0.1:54321/postgres")
    assert env["DATABASE_URL"].endswith("/pc_support_test_runtime")
    assert "TEST_DATABASE_URL" not in env
    assert "PC_CLIENT_ALLOW_SHARED_TEST_DB" not in env
    assert env["PC_CLIENT_TEST_DB_TEMPLATE"] == "0"
    assert env["PC_CLIENT_KEEP_TEST_DB"] == "0"


@pytest.mark.parametrize("url", [
    "postgresql+asyncpg://test_admin@remote/postgres",
    "postgresql+asyncpg://test_admin@127.0.0.1:54321/production",
])
def test_child_environment_rejects_nonlocal_or_nonadmin_database(url):
    with pytest.raises(ValueError):
        child_environment({}, url)


def test_output_redaction_keeps_runtime_secret_out_of_evidence():
    secret = "synthetic-runtime-secret"
    assert redact(f"url=postgresql://admin:{secret}@127.0.0.1 error={secret}", secret) == (
        "url=postgresql://admin:[REDACTED]@127.0.0.1 error=[REDACTED]"
    )


def test_redaction_without_a_secret_preserves_control_diagnostics():
    assert redact("access denied", "") == "access denied"


def test_cleanup_path_must_be_a_dedicated_child_of_run_root(tmp_path):
    root = tmp_path / "runs"
    root.mkdir()
    child = root / "pg-test-123"
    child.mkdir()
    assert validate_cluster_path(child, root) == child.resolve()
    for invalid in (root, tmp_path / "outside"):
        with pytest.raises(ValueError):
            validate_cluster_path(invalid, root)


def test_fresh_cluster_is_explicitly_nondurable_and_never_reuses_external_database(tmp_path, monkeypatch, capsys):
    from urllib.parse import urlsplit
    from scripts import run_with_local_postgres as wrapper

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_root = workspace / "owned-runs"
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    for command in ("initdb", "pg_ctl", "postgres"):
        (bin_dir / (command + (".exe" if os.name == "nt" else ""))).touch()
    monkeypatch.setattr(wrapper, "WORKSPACE", workspace)
    monkeypatch.setattr(wrapper, "RUN_ROOT", run_root)
    monkeypatch.setattr(wrapper, "_grant_cluster_owner_access", lambda *_: None)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://external/production")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://external/production")
    monkeypatch.setenv("TEST_DATABASE_ADMIN_URL", "postgresql+asyncpg://external/postgres")
    monkeypatch.setenv("PC_CLIENT_ALLOW_SHARED_TEST_DB", "1")
    events, settings, clusters = [], {}, []

    def control(command, _secret):
        data = Path(command[command.index("-D") + 1])
        assert data.is_relative_to(run_root)
        if Path(command[0]).stem == "initdb":
            data.mkdir()
            (data / "postgresql.conf").write_text("", encoding="utf-8")
            clusters.append(data.parent)
            events.append("initdb")
        else:
            events.append("start" if "start" in command else "stop")

    async def verify(_url, data):
        assert data == clusters[0] / "data"
        events.append("verify")

    def run_child(_command, cwd, environment, _secret):
        assert cwd == workspace
        url = urlsplit(environment["TEST_DATABASE_ADMIN_URL"])
        assert url.hostname == "127.0.0.1" and url.port and url.path == "/postgres"
        assert "external" not in environment["DATABASE_URL"]
        assert "TEST_DATABASE_URL" not in environment and "PC_CLIENT_ALLOW_SHARED_TEST_DB" not in environment
        for line in (clusters[0] / "data" / "postgresql.conf").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                settings[key.strip()] = value.strip().strip("'")
        events.append("child")
        return 0

    monkeypatch.setattr(wrapper, "_control", control)
    monkeypatch.setattr(wrapper, "_verify_cluster", verify)
    monkeypatch.setattr(wrapper, "run_child", run_child)

    assert wrapper.run(["isolated-test-command"], bin_dir) == 0
    assert settings["listen_addresses"] == "127.0.0.1"
    assert {key: settings.get(key) for key in ("fsync", "full_page_writes", "synchronous_commit")} == {
        "fsync": "off", "full_page_writes": "off", "synchronous_commit": "off"}
    assert events == ["initdb", "start", "verify", "child", "stop"]
    assert not clusters[0].exists()
    assert "disposable nondurable cluster; no crash-durability guarantees" in capsys.readouterr().out


def _process_alive(pid: int) -> bool:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        return code.value == 259
    finally:
        kernel.CloseHandle(handle)


def _cleanup_test_process(pid_file: Path):
    if pid_file.exists():
        pid = int(pid_file.read_text())
        if _process_alive(pid):
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=5)


def _tree_script(tmp_path, *, inherited_output: bool, exit_code=0, wait=False):
    grandchild_pid = tmp_path / "grandchild.pid"
    child_pid = tmp_path / "child.pid"
    grandchild = (
        "import os,time; from pathlib import Path; "
        f"path=Path({str(grandchild_pid)!r}); staging=path.with_suffix('.ready'); "
        "staging.write_text(str(os.getpid())); staging.replace(path); time.sleep(30)"
    )
    script = (
        "import os,subprocess,sys,time; from pathlib import Path; "
        f"Path({str(child_pid)!r}).write_text(str(os.getpid())); "
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}]"
        + ("); " if inherited_output else ", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); ")
    )
    # Wait for the actual grandchild to run before letting the child exit.
    script += f"\nwhile not Path({str(grandchild_pid)!r}).exists(): time.sleep(.01)\n"
    script += "print('child ready', flush=True)\n"
    script += "time.sleep(30)\n" if wait else f"sys.exit({exit_code})\n"
    return [sys.executable, "-c", script], child_pid, grandchild_pid


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object ownership")
@pytest.mark.parametrize("exit_code", [0, 7])
def test_child_exit_cleans_descendants_even_with_redirected_output(tmp_path, exit_code):
    command, child_pid, grandchild_pid = _tree_script(tmp_path, inherited_output=False, exit_code=exit_code)
    try:
        assert run_child(command, tmp_path, dict(os.environ), "synthetic-secret") == exit_code
        assert not _process_alive(int(child_pid.read_text()))
        assert not _process_alive(int(grandchild_pid.read_text()))
    finally:
        _cleanup_test_process(child_pid)
        _cleanup_test_process(grandchild_pid)


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object ownership")
def test_inherited_stdout_does_not_wait_for_grandchild_eof(tmp_path):
    command, child_pid, grandchild_pid = _tree_script(tmp_path, inherited_output=True)
    interrupted = threading.Event()
    expired = threading.Event()

    def watchdog():
        if not interrupted.wait(5):
            expired.set()
            _cleanup_test_process(child_pid)
            _cleanup_test_process(grandchild_pid)

    thread = threading.Thread(target=watchdog, daemon=True)
    thread.start()
    try:
        result = run_child(command, tmp_path, dict(os.environ), "synthetic-secret")
        assert not expired.is_set(), "inherited stdout blocked after direct child exit"
        assert result == 0
        assert not _process_alive(int(grandchild_pid.read_text()))
    finally:
        interrupted.set()
        thread.join(timeout=1)
        _cleanup_test_process(child_pid)
        _cleanup_test_process(grandchild_pid)


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object ownership")
def test_cancellation_cleans_child_and_grandchild(tmp_path):
    command, child_pid, grandchild_pid = _tree_script(tmp_path, inherited_output=False, wait=True)
    stop = threading.Event()
    forced_cleanup = threading.Event()

    def cancel_after_ready():
        deadline = time.monotonic() + 5
        while not stop.wait(.01) and time.monotonic() < deadline:
            if grandchild_pid.exists():
                _thread.interrupt_main()
                if not stop.wait(2):
                    forced_cleanup.set()
                    _cleanup_test_process(child_pid)
                    _cleanup_test_process(grandchild_pid)
                return

    thread = threading.Thread(target=cancel_after_ready, daemon=True)
    thread.start()
    try:
        with pytest.raises(KeyboardInterrupt):
            run_child(command, tmp_path, dict(os.environ), "synthetic-secret")
        assert not forced_cleanup.is_set(), "cancellation could not release the child's pipe"
        assert not _process_alive(int(child_pid.read_text()))
        assert not _process_alive(int(grandchild_pid.read_text()))
    finally:
        stop.set()
        thread.join(timeout=1)
        _cleanup_test_process(child_pid)
        _cleanup_test_process(grandchild_pid)


def test_child_output_redacts_secret_split_across_writes_and_stderr(tmp_path, capsys):
    secret = "synthetic-sensitive-runtime-value"
    code = (
        "import sys,time; "
        f"sys.stdout.write({secret[:13]!r}); sys.stdout.flush(); time.sleep(.05); "
        f"sys.stdout.write({secret[13:]!r} + '\\n'); sys.stdout.flush(); "
        f"sys.stderr.write('stderr=' + {secret!r} + '\\n'); sys.stderr.flush(); "
        "sys.stdout.buffer.write('Привет'.encode('utf-8')); sys.stdout.flush()"
    )
    assert run_child([sys.executable, "-c", code], tmp_path, dict(os.environ), secret) == 0
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert captured.out == "[REDACTED]\nstderr=[REDACTED]\nПривет"


def test_child_output_without_newline_is_live(tmp_path, monkeypatch):
    receipt = tmp_path / "output-received"

    class Output(io.StringIO):
        def write(self, text):
            count = super().write(text)
            if "ready-without-newline" in self.getvalue():
                receipt.touch()
            return count

    output = Output()
    code = (
        "import sys,time; from pathlib import Path; "
        "print('ready-without-newline', end='', flush=True); "
        "deadline=time.monotonic()+3\n"
        f"while not Path({str(receipt)!r}).exists() and time.monotonic()<deadline: time.sleep(.01)\n"
        f"sys.exit(0 if Path({str(receipt)!r}).exists() else 9)"
    )
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", output)
        result = run_child([sys.executable, "-c", code], tmp_path, dict(os.environ), "a" * 64)

    assert result == 0, "plain output was buffered until process exit"
    assert output.getvalue() == "ready-without-newline"


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object ownership")
@pytest.mark.parametrize("failure_stage", ["queue", "decoder", "thread", "start"])
def test_setup_cancellation_leaves_no_launched_child(tmp_path, monkeypatch, failure_stage):
    native_process = owned_child_process._WindowsProcess
    launched = []

    def launch(*args):
        process = native_process(*args)
        get_pid = process.kernel.GetProcessId
        get_pid.argtypes = [ctypes.c_void_p]
        get_pid.restype = ctypes.c_ulong
        launched.append((get_pid(process.process), process))
        return process

    def cancelled(*args, **kwargs):
        raise KeyboardInterrupt("synthetic setup cancellation")

    monkeypatch.setattr(owned_child_process, "_WindowsProcess", launch)
    if failure_stage == "queue":
        monkeypatch.setattr(owned_child_process.queue, "SimpleQueue", cancelled)
    elif failure_stage == "decoder":
        monkeypatch.setattr(owned_child_process.io, "IncrementalNewlineDecoder", cancelled)
    elif failure_stage == "thread":
        monkeypatch.setattr(owned_child_process.threading, "Thread", cancelled)
    else:
        monkeypatch.setattr(owned_child_process.threading.Thread, "start", cancelled)

    try:
        with pytest.raises(KeyboardInterrupt, match="synthetic setup cancellation"):
            run_child([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, dict(os.environ), "")
        assert not any(_process_alive(pid) for pid, _ in launched)
    finally:
        for _, process in launched:
            process.close()
            process.stdout.close()


@pytest.mark.parametrize("legacy_encoding", ["ascii", "cp1251"])
def test_main_emits_utf8_with_legacy_redirected_streams(legacy_encoding):
    code = (
        "import sys; from scripts import run_with_local_postgres as wrapper; "
        "wrapper.run=lambda command, bin_dir: ("
        "print('✓ Прогресс 漢字', flush=True), "
        "print('stderr ✓ Прогресс 漢字', file=sys.stderr, flush=True), 0)[-1]; "
        "sys.argv=['run_with_local_postgres.py', '--', 'unused-command']; "
        "raise SystemExit(wrapper.main())"
    )
    env = dict(os.environ, PYTHONIOENCODING=legacy_encoding, PYTHONUTF8="0")
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                            env=env, capture_output=True, timeout=10)

    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout.decode("utf-8").splitlines() == ["✓ Прогресс 漢字"]
    assert result.stderr.decode("utf-8").splitlines() == ["stderr ✓ Прогресс 漢字"]
