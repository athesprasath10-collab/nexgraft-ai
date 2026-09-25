"""Start NEXGRAFT AI locally:  python run.py  [--no-browser] [--port 8000]"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))


def main() -> None:
    from nexgraft.config import FRONTEND_DIST, settings

    parser = argparse.ArgumentParser(description="Run the NEXGRAFT AI local server")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes (development)")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        sys.exit("Missing dependencies. Run: pip install -r backend/requirements.txt")

    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    print("\n  NEXGRAFT AI — One Platform. Multiple Experts. One Intelligent Solution.")
    print(f"  Local workspace: {url}")
    if not FRONTEND_DIST.is_dir():
        print("  ! Frontend not built yet: cd frontend && npm install && npm run build")
    print(f"  Ollama: {settings.ollama_url}   (Ctrl+C to stop)\n")

    if not args.no_browser and FRONTEND_DIST.is_dir():
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        "nexgraft.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(ROOT / "backend")] if args.reload else None,
        app_dir=str(ROOT / "backend"),
        log_level="info",
    )


if __name__ == "__main__":
    main()
