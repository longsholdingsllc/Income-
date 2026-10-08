"""Autopilot server – assembled from parts for deploy size limits."""
from pathlib import Path
_p = Path(__file__).resolve().parent
_code = (_p / "server_part1.py").read_text() + (_p / "server_part2.py").read_text()
exec(compile(_code, str(_p / "server.py"), "exec"), globals())
