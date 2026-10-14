"""Select the project's interpreter before importing scan dependencies."""
import importlib.util
from pathlib import Path
import subprocess
import sys


def ensure_environment():
    if all(importlib.util.find_spec(name) is not None for name in ("PIL", "pymupdf")):
        return
    root = Path(__file__).resolve().parents[1]
    interpreter = root / ".venv" / "Scripts" / "python.exe"
    if interpreter.exists() and interpreter.resolve() != Path(sys.executable).resolve():
        result = subprocess.run([str(interpreter), str(root / "src" / "app.py"), *sys.argv[1:]])
        raise SystemExit(result.returncode)
    print("Die Scanbibliotheken fehlen. Bitte run_ctc.bat im Versionsordner starten; "
          "es richtet die lokale Python-Umgebung ein.")
    raise SystemExit(1)
