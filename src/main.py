import argparse

# Flexible import: works both as "python -m src.main" and "python src/main.py"
try:
    # when run as module
    from .scheduler import run_once, run_interval
except Exception:
    # when run as script
    from src.scheduler import run_once, run_interval

def main():
    ap = argparse.ArgumentParser(description="AI Coin Hunter")
    ap.add_argument("cmd", choices=["once", "interval"], help="Запустить разово или по расписанию")
    args = ap.parse_args()
    if args.cmd == "once":
        run_once()
    else:
        run_interval()

if __name__ == "__main__":
    main()
