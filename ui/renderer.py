import io
import utils
import portfolio

from colorama import Fore, Style, Back
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Callable


@dataclass
class CellData:
    value: str
    color: str = Fore.RESET

@dataclass
class ColumnFormatter:
    header: str
    width: int

    # function that takes a thing and produces a printable string for it
    generator: Callable[[object], CellData] = lambda v: CellData(str(v))

    def generate_string(self, input) -> str:
        cell_data = self.generator(input)
        return cell_data.value

def format_number(value) -> str:
        return str(abs(utils.round_value(value, "math", 2)))

def format_gl(value: float, is_currency: bool = True) -> str:
        change_symbol = "+" if value >= 0 else "-"
        if is_currency:
            change_symbol += "$"

        return change_symbol + format_number(value)

# TODO: refactor all formatters to only require a PortfolioEntry?
_stock_column_formatters = {
    "Ticker" : ColumnFormatter("Ticker", 9, lambda stock: CellData(stock.symbol)),
    "Current Price" : ColumnFormatter("Last", 12, lambda stock: CellData(format_number(stock.curr_value))),
    "Daily Change Amount": ColumnFormatter("Chg", 12, lambda stock: CellData(format_gl(stock.change_amount), Fore.GREEN if stock.change_amount >= 0 else Fore.RED)),
    "Daily Change Percentage": ColumnFormatter("Chg%", 10, lambda stock: CellData(format_gl(stock.change_percentage, False), Fore.GREEN if stock.change_percentage >= 0 else Fore.RED)),
    "Low": ColumnFormatter("Low", 12, lambda stock: CellData(format_number(stock.low))),
    "High": ColumnFormatter("High", 12, lambda stock: CellData(format_number(stock.high))),
    "Daily Average Price": ColumnFormatter("Avg", 12, lambda stock: CellData(format_number(stock.average))),
}

_portfolio_column_formatters = {
    "Stocks Owned": ColumnFormatter("Owned", 9, lambda entry: CellData(format_number(entry.count))),
    "Gains per Share": ColumnFormatter("G/L/S", 12, lambda entry: CellData(format_gl(entry.gains_per_share), Fore.GREEN if entry.gains_per_share >= 0 else Fore.RED)),
    "Current Market Value": ColumnFormatter("Mkt V", 12, lambda entry: CellData(format_number(entry.holding_market_value))),
    "Average Buy Price": ColumnFormatter("Buy", 12, lambda entry: CellData(format_number(entry.average_cost), Fore.GREEN if entry.average_cost <= entry.stock.curr_value else Fore.RED)),
    "Total Share Gains": ColumnFormatter("G/L/T", 12, lambda entry: CellData(format_gl(entry.gains), Fore.GREEN if entry.gains >= 0 else Fore.RED)),
    "Total Share Cost": ColumnFormatter("Cost", 12, lambda entry: CellData(format_number(entry.cost_basis))),
}

_ticker_column_formatters = {
    "Ticker" : ColumnFormatter("Ticker", 12, lambda info: CellData(info.get("symbol"))),
    "Current Price" : ColumnFormatter("Last", 12, lambda info: CellData(format_number(info.get("regularMarketPrice")))),
    "Bid Ask": ColumnFormatter("Bid/Ask", 20, lambda info: CellData(format_number(info.get("bid")) + "/" + format_number(info.get("ask")))),
    "200 Day Average" : ColumnFormatter("200D Avg", 12, lambda info: CellData(format_number(info.get("twoHundredDayAverage")))),
    #"Daily Change Percentage": ColumnFormatter("Chg%", 10, lambda info: CellData(format_number(info.get("")))),
    #"Daily Change Amount": ColumnFormatter("Chg", 12, lambda info: CellData(format_number(info.get("regularMarketPrice")))),
    #"Daily Change Percentage": ColumnFormatter("Chg%", 10, lambda info: CellData(format_number(info.get("")))),
    "Low": ColumnFormatter("Low", 12, lambda info: CellData(format_number(info.get("regularMarketDayLow")))),
    "High": ColumnFormatter("High", 12, lambda info: CellData(format_number(info.get("regularMarketDayHigh")))),
    #"Daily Average Price": ColumnFormatter("Avg", 12, lambda info: CellData(format_number(info.get("")))),
    "52 Week High": ColumnFormatter("52 wk High", 12, lambda info: CellData(format_number(info.get("fiftyTwoWeekHigh")))),
    "Volume": ColumnFormatter("Avg Vol", 12, lambda info: CellData(format_number(info.get("averageVolume")))),
    "10 Day Volume": ColumnFormatter("10 Day Vol", 12, lambda info: CellData(format_number(info.get("averageDailyVolume10Day")))),
}

# require portfolio passed in
class Renderer(metaclass=utils.Singleton):
    def __init__(self, rounding: str, *args, **kwargs):
        self.mode = rounding
        return

    def _print_gains(self, portfolio: portfolio.Portfolio, gain: float, timespan):
        positive_gain = gain >= 0
        gain_symbol = "+" if positive_gain else "-"
        gain_verboge = "Gained" if positive_gain else "Lost"

        print("{:25}".format("Value " + gain_verboge + " " + timespan + ": "), end="")
        print(Fore.GREEN if positive_gain else Fore.RED, end="")
        print(
            "{:13}".format(
                gain_symbol + "$" + str(abs(utils.round_value(gain, self.mode, 2)))
            )
            + "{:13}".format(
                gain_symbol
                + str(
                    abs(
                        utils.round_value(
                            gain / portfolio.cost_value * 100 if portfolio.cost_value != 0 else 0, self.mode, 2
                        )
                    )
                )
                + "%"
            )
        )
        print(Style.RESET_ALL, end="")
        return

    def _print_overall_summary(self, portfolio: portfolio.Portfolio):
        print(
            "\n"
            + "{:25}".format("Current Time: ")
            + "{:13}".format(datetime.now().strftime("%A %b %d, %Y - %I:%M:%S %p"))
        )
        print(
            "{:25}".format("Total Cost: ")
            + "{:13}".format("$" + format_number(portfolio.cost_value))
        )
        print(
            "{:25}".format("Total Value: ")
            + "{:13}".format("$" + format_number(portfolio.market_value))
        )

        # print daily value
        value_gained_day = (
            portfolio.market_value - portfolio.open_market_value
        )
        self._print_gains(portfolio, value_gained_day, "Today")

        # print overall value
        value_gained_all = portfolio.market_value - portfolio.cost_value
        self._print_gains(portfolio, value_gained_all, "Overall")
        return

    def print_entries(self, portfolio: portfolio.Portfolio, print_cols = list(_stock_column_formatters.keys()) + list(_portfolio_column_formatters.keys())):
        # print the heading
        heading = "\n\t"
        divider = "\t"
        for col in print_cols:
            column = _stock_column_formatters.get(col) or _portfolio_column_formatters.get(col)
            heading += ("{:" + str(column.width) + "}").format(column.header)
            divider += "-" * column.width
        print(heading + "\n" + divider)

        # now print every portfolio entry
        for i, entry in enumerate(portfolio.stocks.values()):
            stock = entry.stock
            line = "\t"

            highlight_color = Back.LIGHTBLACK_EX if i % 2 == 0 else Back.RESET
            line += highlight_color

            for i, col in enumerate(print_cols):
                col_formatter = _stock_column_formatters.get(col) 
                
                is_stock = col_formatter != None
                if not is_stock:
                    col_formatter = _portfolio_column_formatters.get(col)

                cell_data = col_formatter.generator(stock if is_stock else entry)
                line += cell_data.color + ("{:" + str(col_formatter.width) + "}").format(cell_data.value)

            # print the entry
            line += Style.RESET_ALL
            print(line, flush = True)

        self._print_overall_summary(portfolio)

        return

    def print_graphs(self, graphs: list):
        for graph in graphs:
            graph.draw()
        return

    # TODO: this should just reuse the existing print_entries method
    def print_tickers(self, portfolio: portfolio.Portfolio, print_cols = list(_stock_column_formatters.keys())):
        up_arrow_code = '\033[A'
        complete_line = ''

        # print the heading
        heading = "\n\t"
        divider = "\t"
        for col in print_cols:
            column = _stock_column_formatters.get(col) or _portfolio_column_formatters.get(col)
            heading += ("{:" + str(column.width) + "}").format(column.header)
            divider += "-" * column.width
        complete_line += f'{heading}\n{divider}'
        end = f'{up_arrow_code}{up_arrow_code}'

        # now print every portfolio entry
        for i, entry in enumerate(portfolio.stocks.values()):
            stock = entry.stock

            complete_line += '\n\t'
            complete_line += Back.LIGHTBLACK_EX if i % 2 == 0 else Back.RESET

            for i, col in enumerate(print_cols):
                col_formatter = _stock_column_formatters.get(col) 
                cell_data = col_formatter.generator(stock)
                complete_line += cell_data.color + ("{:" + str(col_formatter.width) + "}").format(cell_data.value)

            # print the entry
            complete_line += Style.RESET_ALL
            end += up_arrow_code
        
        complete_line += "\n"
        print(complete_line, flush= True, end= f'\r{end}')

    def print_single_ticker(self, ticker):
        line = "\n"
        
        for i, col_formatter in enumerate(_ticker_column_formatters.values()):
            if (col_formatter is None):
                continue

            cell_data = col_formatter.generator(ticker.info)
            line += f'{col_formatter.header}: '
            line += cell_data.color + ("{:" + str(col_formatter.width) + "}").format(cell_data.value)
            line += Style.RESET_ALL

            if ((i + 1) % 3 == 0):
                line += "\n"

        print(line, flush = True)