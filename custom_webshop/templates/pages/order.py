import frappe
from frappe import _
from webshop.webshop.doctype.webshop_settings.webshop_settings import show_attachments

def get_context(context):
    context.no_cache = 1
    context.show_sidebar = True

    name = frappe.form_dict.name
    if not name:
        frappe.throw(_("Missing document name in URL"))

    # 1) determine type
    if frappe.db.exists("Sales Invoice", name):
        doctype = "Sales Invoice"
    elif frappe.db.exists("Sales Order", name):
        doctype = "Sales Order"
    elif frappe.db.exists("Delivery Note", name):
        doctype = "Delivery Note"
    else:
        frappe.throw(_("Document {0} not found").format(name))

    # 2) load the document
    doc = frappe.get_doc(doctype, name)
    context.doctype = doctype
    context.doc = doc

    # 3) attachments
    if show_attachments():
        context.attachments = frappe.get_all(
            "File",
            fields=["name","file_name","file_url","is_private"],
            filters={
                "attached_to_doctype": doctype,
                "attached_to_name": name,
                "is_private": 0
            }
        )
    else:
        context.attachments = []

    # 4) print & checkout settings
    ws = frappe.get_doc("Webshop Settings")
    context.enabled_checkout = ws.enable_checkout
    context.print_format = (
        frappe.db.get_value(
            "Property Setter",
            {"property": "default_print_format", "doc_type": doctype},
            "value"
        ) or "Standard"
    )

    # 5) loyalty points
    loyalty = frappe.db.get_value("Customer", doc.customer_name, "loyalty_program")
    if loyalty:
        from erpnext.accounts.doctype.loyalty_program.loyalty_program \
            import get_loyalty_program_details_with_points
        pts = get_loyalty_program_details_with_points(doc.customer_name, loyalty)
        context.available_loyalty_points = int(pts.get("loyalty_points") or 0)
    else:
        context.available_loyalty_points = 0

    # 6) permissions
    if not frappe.has_website_permission(doc):
        frappe.throw(_("Not Permitted"), frappe.PermissionError)

    # 7) custom buttons (only for Sales Order)
    context.show_cancel_order = (
        doctype == "Sales Order"
        and doc.docstatus == 1
        and doc.status not in ("Cancelled", "Completed")
    )
    context.show_make_delivery = (
        doctype == "Sales Order"
        and doc.docstatus == 1
        and doc.status in ("To Deliver", "To Deliver and Bill")
        and not frappe.db.exists("Delivery Note", {"against_sales_order": doc.name})
    )
    # 7b) show_make_invoice: True if no submitted invoice exists for this SO
    context.show_make_invoice = (
        doctype == "Sales Order"
        and doc.docstatus == 1
        and not frappe.db.exists("Sales Invoice Item", {"sales_order": doc.name})
    )

    # 8) show_check_momo_payment: Only for Sales Invoice, unpaid/partly paid
    context.show_check_momo_payment = (
        doctype == "Sales Invoice"
        and doc.docstatus == 1
        and doc.status in ("Unpaid", "Partly Paid")
    )

    # In get_context()
    context.show_partial_momo_button = (
        context.doctype == "Sales Invoice"
        and doc.docstatus == 1
        and doc.outstanding_amount > 0
    )

    # 9) override the indicator pill colors on SO
    if doctype == "Sales Order" and doc.docstatus == 1:
        if doc.status == "To Deliver and Bill":
            doc.indicator_color = "yellow"
        elif doc.status == "To Deliver":
            doc.indicator_color = "orange"

    return context
