#!/usr/bin/env python3
"""Run the production web build and isolated local backend processes."""
import argparse
import os
import signal
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "services/backend"
RUNTIME = ROOT / "runtime"


def run(args, cwd=ROOT):
    subprocess.run(args, cwd=cwd, check=True)


def alive(name):
    path = RUNTIME / f"{name}.pid"
    if not path.exists():
        return None
    pid = int(path.read_text())
    info = subprocess.run(["ps", "-p", str(pid), "-o", "command="],capture_output=True,text=True)
    if info.returncode != 0:
        return None
    verified = str(ROOT) in info.stdout
    if not verified and name == "web" and "next-server" in info.stdout:
        if Path(f"/proc/{pid}/cwd").exists():
            verified = Path(f"/proc/{pid}/cwd").resolve().is_relative_to(ROOT)
        elif shutil.which("lsof"):
            cwd = subprocess.run(["lsof","-a","-p",str(pid),"-d","cwd","-Fn"],capture_output=True,text=True).stdout
            verified = any(line.startswith("n"+str(ROOT)+"/") for line in cwd.splitlines())
    return pid if verified else None


def start(name, command, cwd, extra_env=None):
    if alive(name):
        print(f"{name}: already running")
        return
    (RUNTIME / "logs").mkdir(parents=True, exist_ok=True)
    with (RUNTIME / "logs" / f"{name}.log").open("a") as log:
        process = subprocess.Popen(command,cwd=cwd,env=os.environ| (extra_env or {}),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    (RUNTIME / f"{name}.pid").write_text(str(process.pid))
    print(f"{name}: started")


def wait_ready(url, timeout=45):
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            with urllib.request.urlopen(url,timeout=2) as response:
                if response.status==200:
                    return
        except Exception:
            pass
        time.sleep(.5)
    raise SystemExit(f"Service did not become ready: {url}. Check runtime/logs.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["up","down","status","prepare-ocr"])
    parser.add_argument("--dev",action="store_true",help="Run the web app with hot reload")
    args = parser.parse_args()
    if args.command=="down":
        for name in ["web","api","chat-worker","ingest-worker"]:
            pid = alive(name)
            if pid:
                os.killpg(pid,signal.SIGTERM)
                print(f"{name}: stopping")
        print("PostgreSQL and its volume are preserved. Use docker compose stop postgres if needed.")
        return
    if args.command=="status":
        for name in ["web","api","chat-worker","ingest-worker"]:
            print(f"{name}: {'running' if alive(name) else 'stopped'}")
        return
    if args.command=="prepare-ocr":
        run(["uv","run","docling-tools","models","download","layout","tableformer","--output-dir",str(RUNTIME/"docling-models")],cwd=BACKEND)
        return
    if all(alive(name) for name in ["web","api","chat-worker","ingest-worker"]):
        print("Tampak-Chat is already running: http://localhost:3010. Stop it before rebuilding or changing run mode.")
        return
    run([sys.executable,str(ROOT/"scripts/bootstrap.py")])
    run(["docker","compose","up","-d","postgres"])
    run(["uv","sync","--frozen","--extra","processing"],cwd=BACKEND)
    run(["pnpm","install","--frozen-lockfile"])
    run(["uv","run","python","-m","app.cli","migrate"],cwd=BACKEND)
    run(["uv","run","python","-m","app.cli","seed"],cwd=BACKEND)
    if not (RUNTIME/"docling-models/docling-project--docling-models").exists():
        run(["uv","run","docling-tools","models","download","layout","tableformer","--output-dir",str(RUNTIME/"docling-models")],cwd=BACKEND)
    python = str(BACKEND/".venv/bin/python")
    start("api",[python,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8100"],BACKEND)
    wait_ready("http://127.0.0.1:8100/api/v1/health")
    for kind in ["chat","ingest"]:
        start(f"{kind}-worker",[python,"-m","app.worker",kind],BACKEND)
    if not args.dev:
        run(["pnpm","--filter","web","build"])
    if args.dev:
        next_bin = str((ROOT/"apps/web/node_modules/next/dist/bin/next").resolve())
        command = ["node",next_bin,"dev","--port","3010","--hostname","127.0.0.1"]
    else:
        web = ROOT/"apps/web"
        standalone = web/".next/standalone/apps/web"
        shutil.copytree(web/".next/static",standalone/".next/static",dirs_exist_ok=True)
        shutil.copytree(web/"public",standalone/"public",dirs_exist_ok=True)
        command = ["node",str(standalone/"server.js")]
    start("web",command,ROOT/"apps/web",{"PORT":"3010","HOSTNAME":"127.0.0.1","TAMPAK_API_URL":"http://127.0.0.1:8100"})
    wait_ready("http://127.0.0.1:3010")
    print("Tampak-Chat is ready: http://localhost:3010")
    print("Admin credentials: private .env file. Logs: runtime/logs/. No credentials are printed.")


if __name__=="__main__":
    main()
