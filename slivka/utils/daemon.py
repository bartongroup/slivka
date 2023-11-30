import os
import signal
import sys


class DummyDaemonContext:
    """ Dummy context that can be used in place of `daemon.DaemonContext`. """
    def __init__(
            self,
            chroot_directory=None,
            working_directory=os.curdir,
            umask=0,
            uid=None,
            gid=None,
            initgroups=False,
            prevent_core=True,
            detach_process=None,
            files_preserve=None,
            pidfile=None,
            stdin=None,
            stdout=None,
            stderr=None,
            signal_map=None):
        self.working_directory = working_directory
        self.pidfile = pidfile
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.signal_map = signal_map or {}
        self._is_open = False

    def open(self):
        if self._is_open:
            return
        os.chdir(self.working_directory)
        for signum, handler in self.signal_map.items():
            if handler is None:
                handler = signal.SIG_IGN
            elif isinstance(handler, str):
                handler = getattr(self, handler)
            signal.signal(signum, handler)
        redirect_stream(sys.stdin, self.stdin)
        redirect_stream(sys.stdout, self.stdout)
        redirect_stream(sys.stderr, self.stderr)
        if self.pidfile is not None:
            self.pidfile.__enter__()
        self._is_open = True

    def close(self):
        if not self._is_open:
            return
        if self.pidfile is not None:
            self.pidfile.__exit__(None, None, None)
        self._is_open = False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def terminate(self, sig_num, stack_frame):
        raise SystemExit(f"Terminating on signal {sig_num}")


def redirect_stream(sys_stream, target_stream):
    if target_stream is None:
        return
    os.dup2(target_stream.fileno(), sys_stream.fileno())
