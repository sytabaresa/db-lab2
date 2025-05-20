#!/usr/bin/env python3
"""
Unbuffered line processor - reads stdin, processes each line immediately,
and streams results to stdout without buffering.
"""

import sys
from typing import Iterable, TextIO
from lock_manager import LockManager


def is_interactive() -> bool:
    """Check if stdout is connected to a terminal (not piped)."""
    return sys.stdout.isatty()


def stream_processor(input_stream: TextIO,
                     output_stream: TextIO,
                     error_stream: TextIO = sys.stderr) -> None:
    """Process lines from input_stream and write to output_stream immediately."""

    lm = LockManager()

    if is_interactive():
        print("Simple lock manager: Starting processing, please execute commands:", file=sys.stderr)  # Status to stderr

    for line in input_stream:
        try:
            # Process the line immediately
            result = lm.process_request_str(line.rstrip('\n'))

            # Handle both single items and iterables
            if isinstance(result, str) or not isinstance(result, Iterable):
                output_stream.write(f"{result}\n")
            else:
                for item in result:
                    output_stream.write(f"{item}\n")

            # Flush after each line to ensure unbuffered output
            output_stream.flush()

        except Exception as e:
            error_stream.write(f"Error processing line: {e}\n")
            error_stream.flush()


def main():
    try:
        stream_processor(sys.stdin, sys.stdout)
    except KeyboardInterrupt:
        sys.stderr.write("\nProcessing interrupted by user\n")
        sys.exit(1)
    except BrokenPipeError:
        # Handle case when output pipe closes early (e.g., head)
        sys.stderr.write("Output pipe closed early\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
