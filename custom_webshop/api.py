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

@frappe.whitelist()
def search_customer():
    """Search customers by name or phone number."""
    phone_number = frappe.form_dict.get("phone_number")

    if not phone_number:
        return {"error": "Phone number is required"}

    try:
        customers = frappe.db.sql("""
            SELECT name, customer_name, mobile_no FROM `tabCustomer`
            WHERE customer_name LIKE %(phone_number)s OR mobile_no LIKE %(phone_number)s
            LIMIT 1
        """, {"phone_number": f"%{phone_number}%"}, as_dict=True)

        if customers:
            frappe.session['customer_phone'] = phone_number
            return customers[0]
        else:
            return {"error": "Customer not found"}
    except Exception as e:
        return {"error": "An unexpected error occurred"}

@frappe.whitelist()
def create_customer(name, phone):
    """Create a new customer with name and phone."""
    if not name or not phone:
        return {"error": "Name and phone are required"}

    try:
        # Check if a customer already exists with this phone
        existing = frappe.db.get_value("Customer", {"mobile_no": phone}, ["name", "customer_name", "mobile_no"], as_dict=True)
        if existing:
            return existing  # Return the already existing customer

        # Create the new customer
        new_customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": name,
            "customer_type": "Individual",
            "mobile_no": phone,
            "customer_group": "Individual",
            "territory": frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
        })
        new_customer.insert(ignore_permissions=True)
        new_customer.save()

        frappe.session['customer_phone'] = phone  # Store the phone in session
        frappe.session['customer_name'] = name  # Store the name in session

        return {
            "customer_name": new_customer.customer_name,
            "mobile_no": new_customer.mobile_no,
            "name": new_customer.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_customer error")
        return {"error": "An unexpected error occurred. Please try again."}

@frappe_whitelist()
def set_customer_phone(phone):
    frappe.session['customer_phone'] = phone
    return {"success": True}

@frappe.whitelist()
def custom_place_order(phone=None):
    from webshop.webshop.shopping_cart.cart import _make_sales_order, _get_cart_quotation, get_shopping_cart_settings
    from webshop.webshop.utils.product import get_web_item_qty_in_stock
    from frappe import _

    if not phone:
        frappe.throw("Customer phone number is required.")

    customer_name = frappe.get_value("Customer", {"mobile_no": phone})
    if not customer_name:
        frappe.throw("Customer with phone number not found.")

    party = frappe.get_doc("Customer", customer_name)
    quotation = _custom_get_cart_quotation()

    quotation.customer = customer_name
    quotation.party_name = customer_name
    
    cart_settings = get_shopping_cart_settings()
    quotation.company = cart_settings.company

        # 👇 Make sure the cart isn't empty
    if not quotation.items:
        frappe.throw("Your cart is empty. Please add items before requesting a quote.")

    quotation.flags.ignore_permissions = True
    quotation.run_method("calculate_taxes_and_totals")
    quotation.save()  # 📝 Just save, don’t submit

    return quotation.name


def _custom_get_cart_quotation():
    from webshop.webshop.shopping_cart.cart import get_shopping_cart_settings

    # Get the logged-in user's cart — NOT the customer's
    quotation = frappe.get_all(
        "Quotation",
        fields=["name"],
        filters={
            "contact_email": frappe.session.user,
            "order_type": "Shopping Cart",
            "docstatus": 0,
        },
        order_by="modified desc",
        limit_page_length=1,
    )

    if quotation:
        qdoc = frappe.get_doc("Quotation", quotation[0].name)
    else:
        company = frappe.db.get_value("E Commerce Settings", None, ["company"])
        qdoc = frappe.get_doc({
            "doctype": "Quotation",
            "naming_series": get_shopping_cart_settings().quotation_series or "QTN-CART-",
            "quotation_to": "Customer",  # Defaults to Customer, update later
            "company": company,
            "order_type": "Shopping Cart",
            "status": "Draft",
            "docstatus": 0,
            "__islocal": 1,
        })

        qdoc.contact_person = frappe.db.get_value("Contact", {"email_id": frappe.session.user})
        qdoc.contact_email = frappe.session.user

        qdoc.flags.ignore_permissions = True
        qdoc.run_method("set_missing_values")

    return qdoc