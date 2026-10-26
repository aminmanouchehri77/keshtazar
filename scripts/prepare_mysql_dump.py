#!/usr/bin/env python3
"""Remove source database selection lines from a MySQL dump."""

import argparse
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description='Prepare a MySQL dump for a cPanel database.'
    )
    parser.add_argument('source', type=Path, help='Source SQL dump file.')
    parser.add_argument('destination', type=Path, help='New output SQL file.')
    args = parser.parse_args()

    source = args.source
    destination = args.destination

    if not source.is_file():
        raise SystemExit('Source SQL dump was not found.')
    if source.resolve() == destination.resolve():
        raise SystemExit('Source and destination must be different files.')
    if not source.name.isascii() or not destination.name.isascii():
        raise SystemExit('Use ASCII file names for both SQL files.')
    if destination.exists():
        raise SystemExit('Destination already exists. Choose a new file name.')

    removed = 0
    try:
        with source.open('r', encoding='utf-8', newline='') as input_file:
            with destination.open('x', encoding='utf-8', newline='') as output_file:
                for line in input_file:
                    statement = line.lstrip()
                    is_database_directive = (
                        statement.upper().startswith(
                            ('CREATE DATABASE', 'DROP DATABASE', 'USE ')
                        )
                        or re.match(
                            r'/\*!\d+\s+DROP\s+DATABASE\b',
                            statement,
                            re.IGNORECASE,
                        )
                    )
                    if is_database_directive:
                        removed += 1
                        continue
                    output_file.write(line)
    except Exception:
        if destination.exists():
            destination.unlink()
        raise

    print('MySQL dump prepared successfully.')
    print('Removed source database directives:', removed)
    print('Output file:', destination.name)


if __name__ == '__main__':
    main()
