import frappe
from webshop.webshop.shopping_cart.cart import get_cart_quotation

def get_context(context):
    cart_data = get_cart_quotation()
    context.doc = cart_data["doc"]
    context.cart_settings = cart_data["cart_settings"]
