__version__ = "0.0.1"

import erpnext.controllers.website_list_for_contact

def custom_permission_override(doc, ptype, user):
    import frappe

    if doc.contact_email == user or doc.owner == user:
        return True

    return False

erpnext.controllers.website_list_for_contact.has_website_permission = custom_permission_override