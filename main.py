import pytz
import plotille
import warnings
import argparse
import contextlib
import multiconfigparser
import time

import portfolio as port

from colorama import Fore, Style
from ui.renderer import Renderer
from ui.commander import Commander


def merge_config(config, args):
    if "General" in config:
        if "independent_graphs" in config["General"]:
            args.independent_graphs = config["General"]["independent_graphs"] == "True"
        if "timezone" in config["General"]:
            args.timezone = config["General"]["timezone"]
        if "rounding_mode" in config["General"]:
            args.rounding_mode = config["General"]["rounding_mode"]

    if "Frame" in config:
        if "width" in config["Frame"]:
            args.width = int(config["Frame"]["width"])
        if "height" in config["Frame"]:
            args.heigth = int(config["Frame"]["height"])

    return


def main():
    config = multiconfigparser.ConfigParserMultiOpt()
    args = parse_args()

    # read config files
    config.read(args.config)

    merge_config(config, args)

    # generate render engine
    render_engine = Renderer(args.rounding_mode)

    # start command loop, the commander handles the exit command
    cmd_runner = Commander(render_engine)
    while True:
        cmd_runner.prompt_and_handle_command()
    
    return


def parse_args():
    parser = argparse.ArgumentParser(description="Options for cliStockTracker.py")
    parser.add_argument(
        "--width",
        type=int,
        help="integer for the width of the chart (default is 80)",
        default=80,
    )
    parser.add_argument(
        "--height",
        type=int,
        help="integer for the height of the chart (default is 20)",
        default=20,
    )
    parser.add_argument(
        "--independent-graphs",
        action="store_true",
        help="show a chart for each stock (default false)",
        default=False,
    )
    parser.add_argument(
        "--timezone",
        type=str,
        help="your timezone (exmple and default: America/New_York)",
        default="America/New_York",
    )
    parser.add_argument(
        "-r",
        "--rounding-mode",
        type=str,
        help="how should numbers be rounded (math | down) (default math)",
        default="math",
    )
    parser.add_argument(
        "--config", type=str, help="path to a config.ini file", default="config.ini"
    )
    parser.add_argument(
        "--portfolio-config",
        type=str,
        help="path to a portfolio.ini file with your list of stonks",
        default="portfolio.ini",
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    main()