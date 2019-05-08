# coding: utf-8
class Config():
    week2days = 7
    mins2hours = 1.0/60.0
    timezone_separator = ':'
    date_range_separator = ':'
    input_time_format = "%Y-%m-%d" + timezone_separator + "%z"
    output_time_format = "%Y-%m-%d"