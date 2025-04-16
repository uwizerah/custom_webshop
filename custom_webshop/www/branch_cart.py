import frappe
from webshop.webshop.shopping_cart.cart import get_cart_quotation

def get_context(context):
    cart_data = get_cart_quotation()
    quotation = cart_data.get("doc")

    if not quotation or quotation.get("docstatus") != 0 or not quotation.items:
        context.doc = None
    else:
        context.doc = quotation

    context.cart_settings = cart_data.get("cart_settings")