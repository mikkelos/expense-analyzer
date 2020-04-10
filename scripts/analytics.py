import pandas as pd

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


def expenses_by_level(df, agg_level=2):
    """ Takes in a dataframe and returns the total aggregated to a level per month"""

    # Extract the main category for each row by taking two first cat_id nums
    df["main_cat"] = df["cat_id"].astype(str).str.slice(0, agg_level)

    # Extract month
    df["trans_month"] = df["trans_date"].dt.month
    df["trans_year"] = df["trans_date"].dt.year

    # Select relevant columns
    df = df[["trans_year", "trans_month", "main_cat",
             "price_net", "item_count", "price_gross", "discount_amt"]]

    # Cast all columns to numeric, making errors NaN
    df["price_net"] = pd.to_numeric(df["price_net"], errors="coerce")
    df["item_count"] = pd.to_numeric(df["item_count"], errors="coerce")
    df["price_gross"] = pd.to_numeric(df["price_gross"], errors="coerce")
    df["discount_amt"] = pd.to_numeric(df["discount_amt"], errors="coerce")

    # Group on main category
    df = df.groupby(["trans_year", "trans_month", "main_cat"]).sum()
    df = df.round(1)

    return df
