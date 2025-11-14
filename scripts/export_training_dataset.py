#!/usr/bin/env python

"""Export combined signal dataset for model training."""

import argparse
import pathlib

from loguru import logger

from src.features.dataset import export_signal_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("artifacts/signal_dataset.parquet"),
        help="Destination file (parquet or csv).",
    )
    parser.add_argument(
        "--db",
        type=pathlib.Path,
        default=None,
        help="Path to SQLite database (defaults to project database).",
    )
    args = parser.parse_args()

    logger.info("Exporting signal dataset to %s", args.output)
    path = export_signal_dataset(args.output, db_path=args.db)
    logger.success("Dataset saved to %s", path)


if __name__ == "__main__":
    main()
