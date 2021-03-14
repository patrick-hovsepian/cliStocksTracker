import argparse
import io
import shlex

from colorama import Fore, Style
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import List, Callable

# TODO: better with a map like columns?
# give each command it's own arg parser?
@dataclass
class CommandType(Enum):
    NONE = auto()
    PRINT_PORTFOLIO_SUMMARY = auto()
    PRINT_PORTFOLIO_GRAPH = auto()
    LIVE_TICKERS = auto()

@dataclass
class Commander:
    curr_command = CommandType.NONE

"""
import argparse
from ConfigParser import ConfigParser
import shlex

parser = argparse.ArgumentParser(description='Short sample app')

parser.add_argument('-a', action="store_true", default=False)
parser.add_argument('-b', action="store", dest="b")
parser.add_argument('-c', action="store", dest="c", type=int)

config = ConfigParser()
config.read('argparse_witH_shlex.ini')
config_value = config.get('cli', 'options')
print 'Config  :', config_value

argument_list = shlex.split(config_value)
print 'Arg List:', argument_list

print 'Results :', parser.parse_args(argument_list)
"""