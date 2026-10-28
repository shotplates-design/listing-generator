import sys

from listing_generator.cli import CommandLine

sys.exit(CommandLine.main(sys.argv[1:]))
