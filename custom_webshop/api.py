import json
import frappe
import re
from frappe.utils import cint
from frappe.utils import nowdate
from frappe.utils import get_fullname
from datetime import datetime
from webshop.webshop.product_data_engine.filters import ProductFiltersBuilder
from webshop.webshop.product_data_engine.query import ProductQuery
from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website
from webshop.webshop.shopping_cart.cart import update_cart as original_update_cart
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

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
            customer = customers[0]
            frappe.session['customer_phone'] = customer.mobile_no
            frappe.session['customer_name'] = customer.customer_name
            frappe.session['branch_operator_email'] = frappe.session.user
            frappe.session['branch_operator_name'] = frappe.db.get_value("User", frappe.session.user, "full_name")

            return customer
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

        bo_email = frappe.session.user
        bo_fullname = frappe.db.get_value("User", bo_email, "full_name")

        # First try finding by email
        bo_customer = frappe.db.get_value("Customer", {"email_id": bo_email}, "name")

        # Fallback: try finding by full name
        if not bo_customer:
            bo_customer = frappe.db.get_value("Customer", {"customer_name": bo_fullname}, "name")

        # Now try to get the address
        bo_address_name = None
        if bo_customer:
            bo_address_name = frappe.db.get_value("Dynamic Link", {
                "link_doctype": "Customer",
                "link_name": bo_customer,
                "parenttype": "Address"
            }, "parent")

        frappe.log_error(f"📦 BO Customer: {bo_customer}, Address: {bo_address_name}", "DEBUG")

        # Link the branch operator's address to the new customer
        if bo_address_name:
            frappe.get_doc({
                "doctype": "Dynamic Link",
                "link_doctype": "Customer",
                "link_name": new_customer.name,
                "parenttype": "Address",
                "parent": bo_address_name
            }).insert(ignore_permissions=True)

        frappe.session['customer_phone'] = phone  # Store the phone in session
        frappe.session['customer_name'] = name  # Store the name in session
        frappe.session['branch_operator_email'] = frappe.session.user  # Store the branch operator email
        frappe.session['branch_operator_name'] = frappe.db.get_value("User", frappe.session.user, "full_name")  # Store the branch operator name

        return {
            "customer_name": new_customer.customer_name,
            "mobile_no": new_customer.mobile_no,
            "name": new_customer.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_customer error")
        return {"error": "An unexpected error occurred. Please try again."}

@frappe.whitelist()
def set_customer_phone(phone):
    frappe.session['customer_phone'] = phone
    frappe.session['branch_operator_email'] = frappe.session.user
    frappe.session['branch_operator_name'] = frappe.db.get_value("User", frappe.session.user, "full_name")
    return {"success": True}

@frappe.whitelist()
def custom_place_order(phone=None):
    from webshop.webshop.shopping_cart.cart import (
        _make_sales_order,
        _get_cart_quotation,
        get_shopping_cart_settings,
    )
    from webshop.webshop.utils.product import get_web_item_qty_in_stock
    from frappe import _

    if not phone:
        frappe.throw("Customer phone number is required.")

    # Get the customer doc
    customer_name = frappe.get_value("Customer", {"mobile_no": phone})
    if not customer_name:
        frappe.throw("Customer with phone number not found.")

    party = frappe.get_doc("Customer", customer_name)
    quotation = _custom_get_cart_quotation()

    # Ensure cart is not empty
    if not quotation.items:
        frappe.throw("Your cart is empty. Please add items before placing an order.")

    # Reassign core fields
    quotation.customer = customer_name
    quotation.party_name = customer_name
    quotation.contact_email = frappe.session.user  # Branch Operator email
    quotation.contact_person = None  # Avoid mismatch error
    quotation.custom_branch_operator_name = get_fullname(frappe.session.user)

    cart_settings = get_shopping_cart_settings()
    quotation.company = cart_settings.company
    quotation.title = customer_name

    quotation.flags.ignore_permissions = True
    quotation.run_method("calculate_taxes_and_totals")
    quotation.submit()

    # Create and insert Sales Order
    sales_order = frappe.get_doc(
        _make_sales_order(quotation.name, ignore_permissions=True)
    )
    sales_order.payment_schedule = []  # Clear if any broken values

    # Optional: stock checks
    if not cint(cart_settings.allow_items_not_in_stock):
        for item in sales_order.get("items"):
            item.warehouse = frappe.db.get_value(
                "Website Item", {"item_code": item.item_code}, "website_warehouse"
            )
            is_stock_item = frappe.db.get_value("Item", item.item_code, "is_stock_item")

            if is_stock_item:
                item_stock = get_web_item_qty_in_stock(item.item_code, "website_warehouse")
                if not cint(item_stock.in_stock):
                    frappe.throw(_("{0} Not in Stock").format(item.item_code))
                if item.qty > item_stock.stock_qty:
                    frappe.throw(
                        _("Only {0} in Stock for item {1}").format(item_stock.stock_qty, item.item_code)
                    )

    sales_order.flags.ignore_permissions = True
    sales_order.insert()
    sales_order.submit()

    return sales_order.name

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

@frappe.whitelist(allow_guest=True)
def update_cart(item_code, qty, additional_notes=None, with_items=False):
    # Call the original function
    result = original_update_cart(item_code, qty, additional_notes, with_items)
    
    # Add custom logic here if needed
    # Example: Log the cart update
    frappe.logger().info(f"Cart updated for item: {item_code}, qty: {qty}")

    return result

@frappe.whitelist(allow_guest=True)
def receive_sms():
    """Receive raw MoMo SMS and record a transaction, pulling its timestamp from the SMS text."""
    data     = frappe.local.form_dict or frappe.get_json(force=True) or {}
    sms_text = data.get("sms_text", "")
    sender   = data.get("sender")

    try:
        # 1) Extract TxID, amount and sender details
        txid_m = re.search(r"TxId[:*]+(\d+)", sms_text)
        amt_m  = re.search(r"received\s+([\d,\.]+)\s*RWF", sms_text)
        name_m = re.search(r"from\s+(.+?)\s*\(\*+(\d{3})\)", sms_text)

        if not (txid_m and amt_m and name_m):
            raise ValueError(f"Missing fields: TxID? {bool(txid_m)}, amount? {bool(amt_m)}, name? {bool(name_m)}")

        txid           = txid_m.group(1)
        amount         = float(amt_m.group(1).replace(",", ""))
        sender_name    = name_m.group(1).strip()
        last_three     = name_m.group(2)

        # 2) Pull the “at YYYY-MM-DD HH:MM:SS” timestamp
        ts_m = re.search(r"\bat\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", sms_text)
        if ts_m:
            ts = datetime.strptime(ts_m.group(1), "%Y-%m-%d %H:%M:%S")
        else:
            ts = datetime.now()

        # 3) Create the MoMo Transaction
        momo = frappe.get_doc({
            "doctype": "MoMo Transaction",
            "transaction_datetime": ts,
            "amount": amount,
            "sender": sender,
            "sender_name": sender_name,
            "sender_last_digits": last_three,
            "transaction_id": txid
        })
        momo.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"status": "ok", "transaction_id": txid}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "MoMo SMS Processing Error")
        return {"status": "error", "message": str(e)}

@frappe.whitelist(allow_guest=True)
def check_momo_payment(sales_order):
    so = frappe.get_doc("Sales Order", sales_order)
    customer_name = so.customer_name.strip().lower()
    last_digits = so.contact_mobile[-3:] if so.contact_mobile else None

    # Match any MoMo transaction where the name is part of the sender_name and the last digits match
    txn = frappe.db.sql("""
        SELECT name, transaction_id, transaction_datetime
        FROM `tabMoMo Transaction`
        WHERE amount = %s
          AND LOWER(sender_name) LIKE %s
          AND sender_last_digits = %s
        ORDER BY transaction_datetime DESC
        LIMIT 1
    """, (so.grand_total, f"%{customer_name}%", last_digits), as_dict=True)

    if not txn:
        return {"status": "Pending"}

    txn = txn[0]  # unpack result

    # Create and submit Sales Invoice if it doesn't exist
    if not frappe.db.exists("Sales Invoice Item", {"sales_order": sales_order}):
        si = make_sales_invoice(sales_order)
        si.mode_of_payment = "Mobile Money"
        si.set_posting_time = 1
        si.posting_date = frappe.utils.today()
        si.insert(ignore_permissions=True)
        si.submit()
    else:
        si = frappe.get_doc("Sales Invoice", {"sales_order": sales_order})

    # Paid To: where the money is going (e.g., mobile money account)
    paid_to = frappe.get_value("Mode of Payment Account", {
        "parent": "Mobile Money",
        "company": so.company
    }, "default_account")

    # Paid From: Customer account (Receivable) — required for party_account
    party_account = frappe.get_value("Account", {
        "account_type": "Receivable",
        "company": so.company,
        "is_group": 0
    })

    payment_entry = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "company": so.company,
        "posting_date": frappe.utils.nowdate(),
        "party_type": "Customer",
        "party": so.customer,
        "party_account": party_account,
        "paid_from": party_account,
        "paid_to": paid_to,          
        "mode_of_payment": "Mobile Money",
        "paid_amount": so.grand_total,
        "received_amount": so.grand_total,
        "reference_no": txn.transaction_id,
        "reference_date": txn.transaction_datetime,
        "references": [{
            "reference_doctype": "Sales Invoice",
            "reference_name": si.name,
            "allocated_amount": so.grand_total
        }]
    })
    payment_entry.insert(ignore_permissions=True)
    payment_entry.submit()

    return {
        "status": "Paid",
        "transaction_id": txn.transaction_id,
        "payment_entry": payment_entry.name,
        "sales_invoice": si.name
    }
