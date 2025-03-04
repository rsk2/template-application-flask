#
# Application-level audit logging.
#
# See https://docs.python.org/3/library/audit_events.html
# https://docs.python.org/3/library/sys.html#sys.addaudithook
# https://www.python.org/dev/peps/pep-0578/
#

import logging
import sys
from typing import Any, Sequence

import api.util.collections

logger = logging.getLogger(__name__)

AUDIT = 32
logging.INFO
logging.addLevelName(AUDIT, "AUDIT")


def init() -> None:
    """Initialize the audit logging module to start
    logging security audit events."""
    sys.addaudithook(handle_audit_event)


def handle_audit_event(event_name: str, args: tuple[Any, ...]) -> None:
    # Define events to log and the arguments to log for each event.
    # For more information about these events and what they mean, see https://peps.python.org/pep-0578/#suggested-audit-hook-locations
    # For the full list of auditable events, see https://docs.python.org/3/library/audit_events.html
    # Define this variable locally so it can't be modified by other modules.

    EVENTS_TO_LOG = {
        # Detect dynamic execution of code objects. This only occurs for explicit
        # calls, and is not raised for normal function invocation.
        "exec": ("code_object",),
        # Detect when a file is about to be opened. path and mode are the usual
        # parameters to open if available, while flags is provided instead of
        # mode in some cases.
        "open": ("path", "mode", "flags"),
        # Detect when a signal is sent to a process.
        "os.kill": ("pid", "sig"),
        # Detect when a file is renamed.
        "os.rename": ("src", "dst", "src_dir_fd", "dst_dir_fd"),
        # Detect when a subprocess is started.
        "subprocess.Popen": ("executable", "args", "cwd", "_"),
        # Detect access to network resources. The address is unmodified from the original call.
        "socket.connect": ("socket", "address"),
        "socket.getaddrinfo": ("host", "port", "family", "type", "protocol"),
        # Detect when new audit hooks are being added.
        "sys.addaudithook": (),
        # Detects URL requests.
        # Don't log data or headers because they may contain sensitive information.
        "urllib.Request": ("url", "_", "_", "method"),
    }

    if event_name not in EVENTS_TO_LOG:
        return

    arg_names = EVENTS_TO_LOG[event_name]
    log_audit_event(event_name, args, arg_names)


# Set the audit hook to be traceable so that coverage module can track calls to it
# The coverage module relies on Python's trace hooks
# (See https://coverage.readthedocs.io/en/7.1.0/howitworks.html#execution)
# According to the docs for sys.addaudithook, the audit hook is only traced if the callable
# has a __cantrace__ member that is set to a true value.
# (See https://docs.python.org/3/library/sys.html#sys.addaudithook)
handle_audit_event.__cantrace__ = True  # type: ignore


def log_audit_event(event_name: str, args: Sequence[Any], arg_names: Sequence[str]) -> None:
    """Log a message but only log recently repeated messages at intervals."""
    extra = {
        f"audit.args.{arg_name}": arg for arg_name, arg in zip(arg_names, args) if arg_name != "_"
    }

    key = (event_name, repr(args))
    if key not in audit_message_count:
        count = 1
    else:
        count = audit_message_count[key] + 1
    audit_message_count[key] = count

    if count > 100 and count % 100 != 0:
        return

    if count > 10 and count % 10 != 0:
        return

    extra["count"] = count

    logger.log(AUDIT, event_name, extra=extra)


audit_message_count = api.util.collections.LeastRecentlyUsedDict()
