"""Command-line parser for the Open Cinema director app."""

import argparse
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


def _port(text):
    """Parse a TCP port (0 to 65535) from text; return it as an int."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid port: {text!r}")
    if not 0 <= value <= 65535:
        raise argparse.ArgumentTypeError(f"port must be 0-65535: {value}")
    return value


def parse_args(argv=None):
    """Parse command-line options (a list of strings, or sys.argv when None).

    Returns an argparse.Namespace with comfyui, host, port, proxy_port,
    proxy_url and data_dir (a Path). Ports are integers from 0 to 65535.
    """
    parser = argparse.ArgumentParser(prog="python -m app", description="Open Cinema director app")
    parser.add_argument("--comfyui", default="http://127.0.0.1:8188", help="ComfyUI base URL")
    parser.add_argument("--host", default="127.0.0.1", help="host the app listens on")
    parser.add_argument("--port", type=_port, default=8000, help="port the app listens on (0-65535)")
    parser.add_argument("--proxy-port", type=_port, default=0, help="port of the API proxy (0-65535, 0 = any)")
    parser.add_argument("--proxy-url", default=None, help="URL of the API proxy")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="folder for stored shots")
    return parser.parse_args(argv)
