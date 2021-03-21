import pytz
import utils
import plotille
import warnings
import webcolors
import autocolors
import time

import numpy as np

from colorama import Fore, Style
from dataclasses import dataclass, field
from datetime import datetime, timedelta

@dataclass
class Graph:
    stocks: list
    colors: list
    width: int = 80
    height: int = 20
    timezone: pytz.timezone = pytz.utc

    def __post_init__(self):
        self.graph = ""
        self.plot: plotille.Figure = plotille.Figure()

        self.plot.width: int = self.width
        self.plot.height: int = self.height
        
        self.plot.color_mode = "rgb"
        self.plot.X_label = "Time"
        self.plot.Y_label = "Value"

        self.start = (
            datetime.now()
            .replace(hour=14, minute=30, second=0)
            .replace(tzinfo=pytz.utc)
            .astimezone(self.timezone)
        )
        self.end = (
            datetime.now()
            .replace(hour=21, minute=0, second=0)
            .replace(tzinfo=pytz.utc)
            .astimezone(self.timezone)
        )
        self.plot.set_x_limits(min_=self.start, max_=self.end)

    def __call__(self):
        return self.graph

    def draw(self):
        print(self.graph)
        return

    def gen_graph(self, auto_colors):
        self.y_min, self.y_max = self.find_y_range()
        self.plot.set_y_limits(min_=self.y_min, max_=self.y_max)

        for i, stock in enumerate(self.stocks):
            if self.colors[i] == None:
                color = webcolors.hex_to_rgb(auto_colors[i % 67])
            elif self.colors[i].startswith("#"):
                color = webcolors.hex_to_rgb(self.colors[i])
            else:
                color = webcolors.hex_to_rgb(
                    webcolors.CSS3_NAMES_TO_HEX[self.colors[i]]
                )

            self.plot.plot(
                [self.start + timedelta(minutes=i) for i in range(len(stock.data))],
                stock.data,
                lc=color,
                label=stock.symbol,
            )

        self.graph = self.plot.show(legend=True)
        return

    def find_y_range(self):
        y_min = 10000000000000  # Arbitrarily large number (bigger than any single stock should ever be worth)
        y_max = 0

        for stock in self.stocks:
            if y_min > min(stock.data):
                y_min = min(stock.data)
            if y_max < max(stock.data):
                y_max = max(stock.data)

        return y_min, y_max
