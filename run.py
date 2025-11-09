# Entry point to run without -m
# Usage:
#   python run.py once
#   python run.py interval
import sys

if __name__ == "__main__":
    # allow "python run.py once"
    try:
        from src.main import main
    except Exception as e:
        print("Import error:", e)
        print("Make sure you're running from the project root where the 'src' folder lives.")
        sys.exit(1)
    main()
