"""Log RAM, GPU and disk usage while supervising a bounded child process."""

import argparse, json, os, shutil, signal, subprocess, time
from pathlib import Path

# Setting =================================================
GIB = 1024 ** 3

# Functions ===============================================
def sample(paths: list[Path]) -> dict:
    mem = {line.split(":")[0]: int(line.split()[1]) * 1024
           for line in Path("/proc/meminfo").read_text().splitlines()}
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu",
                          "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
    disks = {str(p): dict(zip(("total", "used", "free"), shutil.disk_usage(p))) for p in paths}
    return {"time": time.time(), "ram_available": mem["MemAvailable"], "ram_total": mem["MemTotal"],
            "swap_used": mem["SwapTotal"] - mem["SwapFree"], "gpu": gpu.stdout.strip(),
            "gpu_error": gpu.stderr.strip() if gpu.returncode else None, "disks": disks,
            "diskstats": Path("/proc/diskstats").read_text()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--disk", type=Path, action="append", required=True)
    parser.add_argument("--ram-floor-gib", type=float, default=4)
    parser.add_argument("--disk-floor-gib", type=float, default=20)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("A supervised command is required")
    args.log.parent.mkdir(parents=True, exist_ok=True)
    proc = None
    with args.log.open("a") as log:
        while True:
            state = sample(args.disk)
            unsafe = state["ram_available"] < args.ram_floor_gib * GIB or any(
                d["free"] < args.disk_floor_gib * GIB for d in state["disks"].values())
            gpu_fields = state["gpu"].split(",")
            if len(gpu_fields) == 4:
                unsafe |= float(gpu_fields[3]) >= 88
            state["stop_required"] = unsafe
            log.write(json.dumps(state) + "\n")
            log.flush()
            if unsafe:
                if proc and proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                raise SystemExit("Resource floor/temperature limit reached; child stopped")
            if proc is None:
                proc = subprocess.Popen(command, start_new_session=True)
            try:
                raise SystemExit(proc.wait(timeout=5))
            except subprocess.TimeoutExpired:
                pass

# Run =====================================================
if __name__ == "__main__":
    main()
