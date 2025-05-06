import frappe
from webshop.webshop.shopping_cart.cart import get_cart_quotation
from webshop.webshop.shopping_cart.cart import update_cart as original_update_cart

def get_context(context):
    frappe.local.no_cache = 1
    cart_data = get_cart_quotation()
    context.doc = cart_data["doc"]
    context.cart_settings = cart_data["cart_settings"]
    context.customer_phone = frappe.session.get("customer_phone") or ""
    context.customer_name = frappe.session.get("customer_name") or ""

    # Show customer search ONLY for Branch Operators
    if "Branch Operator" in frappe.get_roles():
        context.show_customer_search = True
    else:
        context.show_customer_search = False


@frappe.whitelist()
def update_cart(item_code, qty, additional_notes=None, with_items=False):
    # Call the original function
    return original_update_cart(item_code, qty, additional_notes, with_items)