import json
import frappe
from frappe.utils import cint
from webshop.webshop.product_data_engine.filters import ProductFiltersBuilder
from webshop.webshop.product_data_engine.query import ProductQuery
from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website

@frappe.whitelist(allow_guest=True)
def get_product_filter_data(query_args=None):

    # Parse query_args if it's a string
    if isinstance(query_args, str):
        query_args = json.loads(query_args)

    query_args = frappe._dict(query_args or {})
    search = query_args.get("search")
    field_filters = query_args.get("field_filters", {})
    attribute_filters = query_args.get("attribute_filters", {})
    start = cint(query_args.get("start", 0))
    item_group = query_args.get("item_group")
    from_filters = query_args.get("from_filters", False)

    # Reset start if `from_filters` is True
    if from_filters:
        start = 0

    # Fetch the logged-in user's assigned warehouse
    assigned_warehouse = frappe.db.get_value(
        "User Permission",
        {"user": frappe.session.user, "allow": "Warehouse"},
        "for_value"
    )

    # If no assigned warehouse, return the original Webshop data
    if not assigned_warehouse:
        frappe.log_error("Custom Webshop: No assigned warehouse; returning original data")
        return _get_original_webshop_data(query_args)

    # Get subcategories for the item group
    sub_categories = []
    if item_group:
        sub_categories = get_child_groups_for_website(item_group, immediate=True)

    # Fetch products using the ProductQuery engine
    engine = ProductQuery()
    try:
        result = engine.query(
            attribute_filters, field_filters, search_term=search, start=start, item_group=item_group
        )
    except Exception as e:
        frappe.log_error(f"Custom Webshop: Product query failed - {e}")
        return {"exc": "Something went wrong!"}

    # Fetch stock availability for all items in the assigned warehouse
    item_stock_map = frappe.db.get_all(
        "Bin",
        filters={"warehouse": assigned_warehouse},
        fields=["item_code", "actual_qty"],
    )

    # Convert stock data to a dictionary for quick lookup
    stock_lookup = {stock["item_code"]: stock["actual_qty"] for stock in item_stock_map}

    # Update `in_stock` for items based on stock in assigned warehouse
    for item in result.get("items", []):
        item_code = item.get("item_code")
        stock_qty = stock_lookup.get(item_code, 0)
        item["in_stock"] = stock_qty > 0  

    return {
        "items": result.get("items", []),
        "filters": {},
        "settings": engine.settings,
        "sub_categories": sub_categories,
        "items_count": result.get("items_count"),
    }

def _get_original_webshop_data(query_args):
    """Call the original Webshop API function to avoid recursion issues."""
    try:
        return frappe.get_attr("webshop.webshop.api.get_product_filter_data")(query_args)
    except Exception as e:
        frappe.log_error(f"Failed to fetch original Webshop data: {e}")
        return {"error": "Failed to fetch Webshop product data."}

@frappe.whitelist(allow_guest=True)
def get_guest_redirect_on_action():
    return frappe.db.get_single_value("Webshop Settings", "redirect_on_action")
