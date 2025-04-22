import frappe
from webshop.webshop.shopping_cart.cart import get_cart_quotation

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