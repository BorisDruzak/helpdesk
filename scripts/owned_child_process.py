"""Run a command with redacted output and an owned process lifetime."""
from __future__ import annotations

import codecs
import ctypes
from ctypes import wintypes
import io
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import threading
import time


class _BasicLimits(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                ("max_working_set", ctypes.c_size_t), ("active_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD)]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "read_operations", "write_operations", "other_operations", "read_bytes", "write_bytes", "other_bytes")]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", _BasicLimits), ("io", _IoCounters),
                ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]


class _Accounting(ctypes.Structure):
    _fields_ = [("user_time", ctypes.c_int64), ("kernel_time", ctypes.c_int64),
                ("period_user_time", ctypes.c_int64), ("period_kernel_time", ctypes.c_int64),
                ("page_faults", wintypes.DWORD), ("total", wintypes.DWORD),
                ("active", wintypes.DWORD), ("terminated", wintypes.DWORD)]


class _StartupInfo(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("reserved", wintypes.LPWSTR),
                ("desktop", wintypes.LPWSTR), ("title", wintypes.LPWSTR),
                *[(name, wintypes.DWORD) for name in (
                    "x", "y", "width", "height", "x_chars", "y_chars", "fill", "flags")],
                ("show", wintypes.WORD), ("reserved_size", wintypes.WORD),
                ("reserved_data", ctypes.c_void_p), ("stdin", wintypes.HANDLE),
                ("stdout", wintypes.HANDLE), ("stderr", wintypes.HANDLE)]


class _StartupInfoEx(ctypes.Structure):
    _fields_ = [("startup", _StartupInfo), ("attributes", ctypes.c_void_p)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [("process", wintypes.HANDLE), ("thread", wintypes.HANDLE),
                ("pid", wintypes.DWORD), ("thread_id", wintypes.DWORD)]


def _kernel32():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
        "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
        "QueryInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
        "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
        "InitializeProcThreadAttributeList": ([ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)], wintypes.BOOL),
        "UpdateProcThreadAttribute": ([ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p], wintypes.BOOL),
        "DeleteProcThreadAttributeList": ([ctypes.c_void_p], None),
        "CreateProcessW": ([wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                            wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
                            ctypes.POINTER(_StartupInfoEx), ctypes.POINTER(_ProcessInfo)], wintypes.BOOL),
        "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
        "GetExitCodeProcess": ([wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    return kernel


def _checked(result):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return result


class _WindowsProcess:
    """Atomic job assignment prevents descendants escaping before ownership."""

    def __init__(self, command, cwd, env):
        import msvcrt

        self.kernel = kernel = _kernel32()
        self.job = _checked(kernel.CreateJobObjectW(None, None))
        self.process = None
        self.stdout = None
        read_fd = write_fd = None
        attributes = None
        attributes_initialized = False
        try:
            limits = _ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway.
            _checked(kernel.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
            read_fd, write_fd = os.pipe()
            os.set_inheritable(write_fd, True)
            with open(os.devnull, "rb") as stdin:
                os.set_inheritable(stdin.fileno(), True)
                handles = (wintypes.HANDLE * 2)(msvcrt.get_osfhandle(stdin.fileno()), msvcrt.get_osfhandle(write_fd))
                jobs = (wintypes.HANDLE * 1)(self.job)
                size = ctypes.c_size_t()
                kernel.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
                attributes = ctypes.create_string_buffer(size.value)
                _checked(kernel.InitializeProcThreadAttributeList(attributes, 2, 0, ctypes.byref(size)))
                attributes_initialized = True
                _checked(kernel.UpdateProcThreadAttribute(attributes, 0, 0x20002, handles, ctypes.sizeof(handles), None, None))
                _checked(kernel.UpdateProcThreadAttribute(attributes, 0, 0x2000D, jobs, ctypes.sizeof(jobs), None, None))
                startup = _StartupInfoEx()
                startup.startup.cb = ctypes.sizeof(startup)
                startup.startup.flags = 0x100  # STARTF_USESTDHANDLES
                startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles[0], handles[1], handles[1]
                startup.attributes = ctypes.addressof(attributes)
                info = _ProcessInfo()
                argv = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
                environment = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(env.items(), key=lambda item: item[0].upper())) + "\0\0")
                executable = shutil.which(command[0], path=env.get("PATH")) or command[0]
                _checked(kernel.CreateProcessW(executable, argv, None, None, True,
                                               0x08000000 | 0x00080000 | 0x00000400,
                                               environment, str(cwd), ctypes.byref(startup), ctypes.byref(info)))
                self.process = info.process
                kernel.CloseHandle(info.thread)
            os.close(write_fd)
            write_fd = None
            self.stdout = os.fdopen(read_fd, "rb", buffering=0)
            read_fd = None
        except BaseException:
            self.close()
            raise
        finally:
            if attributes_initialized:
                kernel.DeleteProcThreadAttributeList(attributes)
            for descriptor in (read_fd, write_fd):
                if descriptor is not None:
                    os.close(descriptor)

    def poll(self):
        status = self.kernel.WaitForSingleObject(self.process, 0)
        if status == 258:  # WAIT_TIMEOUT
            return None
        if status != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        code = wintypes.DWORD()
        _checked(self.kernel.GetExitCodeProcess(self.process, ctypes.byref(code)))
        return code.value

    def close_tree(self):
        if self.job is None:
            return
        try:
            _checked(self.kernel.TerminateJobObject(self.job, 1))
            deadline = time.monotonic() + 5
            while True:
                accounting = _Accounting()
                _checked(self.kernel.QueryInformationJobObject(self.job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None))
                if not accounting.active:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("Owned command process tree did not exit")
                time.sleep(.01)
        finally:
            self.kernel.CloseHandle(self.job)
            self.job = None

    def close(self):
        try:
            self.close_tree()
        finally:
            if self.process is not None:
                self.kernel.CloseHandle(self.process)
                self.process = None


class _PosixProcess:
    def __init__(self, command, cwd, env):
        self.process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, start_new_session=True)
        self.stdout = self.process.stdout

    def poll(self):
        return self.process.poll()

    def close_tree(self):
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait(timeout=5)

    def close(self):
        self.close_tree()


def _pump_output(stream, output):
    try:
        while chunk := os.read(stream.fileno(), 65536):
            output.put(chunk)
    finally:
        output.put(None)


def _emit_redacted(buffer: str, secret: str, *, final=False) -> str:
    """Keep the suffix that could be the beginning of a split secret."""
    if not secret:
        print(buffer, end="", flush=True)
        return ""
    while (index := buffer.find(secret)) >= 0:
        print(buffer[:index] + "[REDACTED]", end="", flush=True)
        buffer = buffer[index + len(secret):]
    pending = 0
    if not final:
        for length in range(min(len(buffer), len(secret) - 1), 0, -1):
            if buffer.endswith(secret[:length]):
                pending = length
                break
    length = len(buffer) - pending
    if length:
        print(buffer[:length], end="", flush=True)
    return buffer[length:]


def run_child(command: list[str], cwd: Path, env: dict[str, str], secret: str) -> int:
    if not command:
        raise ValueError("Supply a child command")
    output = queue.SimpleQueue()
    decoder = io.IncrementalNewlineDecoder(codecs.getincrementaldecoder("utf-8")(errors="replace"), translate=True)
    buffer = ""
    eof = tree_closed = False
    result = None
    process = thread = None
    try:
        process = (_WindowsProcess if os.name == "nt" else _PosixProcess)(command, cwd, env)
        thread = threading.Thread(target=_pump_output, args=(process.stdout, output), daemon=True)
        thread.start()
        while True:
            try:
                chunk = output.get(timeout=.05)
                if chunk is None:
                    eof = True
                    buffer += decoder.decode(b"", final=True)
                else:
                    buffer += decoder.decode(chunk)
                buffer = _emit_redacted(buffer, secret, final=eof)
            except queue.Empty:
                pass
            if result is None:
                result = process.poll()
            if result is not None and not tree_closed:
                process.close_tree()
                tree_closed = True
            if eof and result is not None:
                return result
    finally:
        if process is not None:
            try:
                process.close()
            finally:
                if thread is not None and thread.ident is not None:
                    thread.join(timeout=5)
                process.stdout.close()
