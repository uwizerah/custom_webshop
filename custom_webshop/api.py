import frappe

@frappe.whitelist()
def get_product_filter_data(field_filters=None, attribute_filters=None, item_group=None, start=None, from_filters=False):
    try:
        # Fetch the logged-in user's assigned warehouse
        assigned_warehouse = frappe.db.get_value(
            "User Permission",
            {"user": frappe.session.user, "allow": "Warehouse"},
            "for_value"
        )

        # Call the original Webshop API method
        original_method = frappe.get_attr("webshop.webshop.api.get_product_filter_data")
        original_data = original_method(field_filters, attribute_filters, item_group, start, from_filters)

        # If no assigned warehouse, return the original data
        if not assigned_warehouse:
            frappe.log_error("No assigned warehouse; returning original data", "Info")
            return original_data

        # Validate original_data structure
        if not original_data or "message" not in original_data or "items" not in original_data["message"]:
            frappe.log_error("Invalid original_data structure", "Error")
            return {"error": "Invalid product data structure."}

        # Fetch stock availability for all items in the user's warehouse in one query
        item_stock_map = frappe.db.get_all(
            "Bin",
            filters={"warehouse": assigned_warehouse},
            fields=["item_code", "actual_qty"],
        )

        # Convert stock data to a dictionary for quick lookup
        stock_lookup = {stock["item_code"]: stock["actual_qty"] for stock in item_stock_map}

        # Update items in the response based on stock
        for item in original_data["message"]["items"]:
            item_code = item.get("item_code")
            stock_qty = stock_lookup.get(item_code, 0)
            item["in_stock"] = stock_qty > 0  # Set `in_stock` based on stock in user's warehouse

        # Return the updated data
        return original_data

    except Exception as e:
        frappe.log_error(str(e), "Error in get_product_filter_data")
        return {"error": "An error occurred while processing the request."}
