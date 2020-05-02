import pandas as pd
from datetime import date
import calendar

""" Dataframe contains columns:
unit_price_net
cat_id
price_net
discount_type
item_count
item_name
trans_date
registered_datetime
added_by
item_id
price_gross
receipt_id
discount_amt
"""


def add_category_names(df, category_mapping):
    """ Takes in a df containing "cat_id" and joins in the category name """
    return pd.merge(df, category_mapping, on="cat_id", how="left")


def prepare_expenses(df):
    """ Takes in a dataframe and performs basic type casting, adds auxilliary columns etc """

    # Extract year and month
    df["trans_month"] = df["trans_date"].dt.month
    df["trans_year"] = df["trans_date"].dt.year

    # Add three letter month abbreviation
    df['trans_month_short'] = df['trans_month'].apply(lambda x: calendar.month_abbr[x])

    # Cast all columns to numeric, making errors NaN
    df["price_gross"] = pd.to_numeric(df["price_gross"], errors="coerce")
    df["price_net"] = pd.to_numeric(df["price_net"], errors="coerce")
    df["item_count"] = pd.to_numeric(df["item_count"], errors="coerce")
    df["unit_price_net"] = pd.to_numeric(df["unit_price_net"], errors="coerce")
    df["discount_amt"] = pd.to_numeric(df["discount_amt"], errors="coerce")

    return df


def expenses_by_level_and_month(df, agg_level=2):
    """ Takes in a dataframe and returns the total aggregated to a level per month"""

    # Extract the main category for each row by taking two first cat_id nums
    df["main_cat"] = df["cat_id"].astype(str).str.slice(0, agg_level)

    # Select relevant columns
    df = df[["trans_year", "trans_month", "main_cat",
             "price_net", "item_count", "price_gross", "discount_amt"]]

    # Group on main category
    df = df.groupby(["trans_year", "trans_month", "main_cat"]).sum()
    df = df.round(1)

    return df


def expenses_by_month(df, num_months_back=12):
    """Takes a df of expenses, groups them on month and filters
    input:
        df (pd.DataFrame): dataframe of transactions to group and filter
        num_months_back (int): default 12. Number of full months back to include data for

    returns:
        df (pd.DataFrame): filtered and grouped dataframe
    """

    # Filter to last n num_months_back
    current_date = date.today()
    start_month = current_date.month - num_months_back + 1
    start_year = current_date.year

    if start_month == 0:
        start_month = 1
    elif start_month <= 0:
        start_month += 13
        start_year -= 1

    from_date = pd.to_datetime(date(start_year, start_month, 1)).tz_localize("UTC")
    df = df[df["trans_date"] >= from_date]

    # Select relevant columns
    df = df[["trans_year", "trans_month", "price_net", "trans_month_short"]]

    # Group on main category
    df = df.groupby(["trans_year", "trans_month", "trans_month_short"]).sum()
    df = df.round(1)

    return df


def expenses_changes_since_prev(df, join_level):  # , year, month):
    """Takes a df of expenses and groups by join_level in addition to year and month
    input:
        df (pd.DataFrame): dataframe of transactions to group and filter
        join_level (str): The column to which compare with, in addition to year and month

    returns:
        df (pd.DataFrame): filtered and grouped dataframe
    """

    # Group by category, year and month
    df = df.groupby([join_level, "trans_year", "trans_month"]).sum()

    df = df.reset_index()

    # Initialize previous
    df["prev_month"] = 1
    df["prev_year"] = 1

    # Loop through months and calculate previous month and year
    for i, row in df.iterrows():
        prev_month = row["trans_month"] - 1
        prev_year = row["trans_year"]
        if prev_month == 0:
            prev_month = 12
            prev_year = prev_year - 1

        df.at[i, 'prev_month'] = prev_month
        df.at[i, 'prev_year'] = prev_year

    # Join in the spend from last month in a separate column.
    df = df.merge(df, how="left",
        left_on=(join_level, "prev_year", "prev_month"),
        right_on=(join_level, "trans_year", "trans_month")
        )

    # For each category, caluclate the change from last month
    df["change_since_last_month"] = df["price_gross_x"] / df["price_gross_y"] - 1

    # Select relevant columns
    df = df[[join_level, "trans_year_x", "trans_month_x", "price_net_x", "change_since_last_month"]]
    df.columns = [join_level, "trans_year", "trans_month", "price_net", "change_since_last_month"]

    return df
