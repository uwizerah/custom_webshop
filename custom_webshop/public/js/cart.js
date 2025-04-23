let justCreatedCustomer = false;

document.getElementById('search-customer').addEventListener('click', function() {
    const phoneNumber = document.getElementById('customer-phone').value.trim();
    justCreatedCustomer = false;

    if (phoneNumber.length === 10 && phoneNumber.startsWith('07')) {

        frappe.call({
            method: 'custom_webshop.api.search_customer',
            args: { phone_number: phoneNumber },
            callback: function(response) {
                if (response.message && !response.message.error) {
                    const customer = response.message;

                    document.getElementById('customer-name').innerText = customer.customer_name;
                    document.getElementById('customer-phone-display').innerText = customer.mobile_no;

                    sessionStorage.setItem('customer_phone', customer.mobile_no);
                    sessionStorage.setItem('customer_name', customer.customer_name);

                    // Hide the "create customer" form if it exists
                    const form = document.getElementById('create-customer-form');
                    if (form) form.style.display = 'none';

                } else {
                    if (!justCreatedCustomer) {
                        // Customer not found
                        document.getElementById('customer-name').innerText = "Not Found";
                        document.getElementById('customer-phone-display').innerText = "";

                        // Show the "create customer" form if it exists
                        const form = document.getElementById('create-customer-form');
                        if (form) {
                            form.style.display = 'block';
                            document.getElementById('create-phone-number').value = phoneNumber;
                        }
                    }
                }
            },
            error: function(err) {
                console.error("Frappe call failed:", err);
            }
        });
    } else {
        console.warn("Invalid phone number format.");
        alert('Please enter a valid phone number (e.g., 07XXXXXXXX).');
    }
});

// Handle customer creation
if (document.getElementById('create-customer-btn')) {
    document.getElementById('create-customer-btn').addEventListener('click', function () {
        const name = document.getElementById('create-customer-name').value.trim();
        const phone = document.getElementById('create-phone-number').value.trim();
        if (!name || !phone) {
            alert("Please fill out both fields.");
            return;
        }

        frappe.call({
            method: 'custom_webshop.api.create_customer',
            args: { name, phone },
            callback: function (response) {
                if (response.message && !response.message.error) {
                    const customer = response.message;

                    document.getElementById('customer-name').innerText = customer.customer_name;
                    document.getElementById('customer-phone-display').innerText = customer.mobile_no;

                    sessionStorage.setItem('customer_phone', customer.mobile_no);
                    sessionStorage.setItem('customer_name', customer.customer_name);

                    frappe.call({
                        method: 'custom_webshop.api.set_customer_phone',
                        args: { phone: customer.mobile_no },
                        callback: function (response) {
                            console.log("Customer phone set successfully:", response);
                        },
                        error: function (err) {
                            console.error("Failed to set session customer phone:", err);
                        }
                    })

                    justCreatedCustomer = true;

                    document.getElementById('create-customer-form').style.display = 'none';
                    alert("Customer created successfully.");
                } else {
                    alert(response.message.error || "Error creating customer");
                }
            },
            error: function (err) {
                console.error("Error creating customer:", err);
                alert("An error occurred while creating the customer.");
            }
        });
    });
}

//Assign quotation to the customer and not the logged in Branch Operator
document.addEventListener('DOMContentLoaded', function() {
    const customBtn = document.querySelector('.place-order-button');
    if (customBtn) {
        customBtn.addEventListener('click', function() {
            const phone = sessionStorage.getItem('customer_phone');
            if (!phone) {
                alert("Please search or create a customer before placing an order.");
                return;
            }
            frappe.call({
                method: 'custom_webshop.api.custom_place_order',
                args: { phone: phone },
                callback: function(response) {
                    if(!response.exc && response.message) {
                        window.location.href = `/orders/${response.message}`;
                    } else {
                        frappe.msgprint(__('Error placing order. Please try again.'));
                    }
                }
            });
        });
    }
});