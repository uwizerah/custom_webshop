import frappe

def get_context(context):
    name = frappe.form_dict.name
    if not name:
        frappe.throw("Missing order name in URL")

    doc = frappe.get_doc("Sales Order", name)
    context.doc = doc
    context.show_make_pi_button = False
    context.enabled_checkout = True
    context.print_format = "Standard"

    # Optional values your template might expect
    context.attachments = []
    context.available_loyalty_points = 0
