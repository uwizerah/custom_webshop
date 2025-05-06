let justCreatedCustomer = false;

// ✅ Setup shopping_cart.shopping_cart_update only ONCE at start
if (typeof shopping_cart === "undefined") {
    frappe.provide("webshop.webshop.shopping_cart");
}
if (typeof shopping_cart.shopping_cart_update === "undefined") {
    shopping_cart.shopping_cart_update = function (args) {
        return frappe.call({
            type: "POST",
            method: "webshop.webshop.shopping_cart.cart.update_cart",
            args: args,
            callback: function (r) {
                if (!r.exc) {
                    window.location.reload();
                }
            }
        });
    };
}

document.addEventListener('DOMContentLoaded', function() {
    const searchCustomerButton = document.getElementById('search-customer');
    const createCustomerButton = document.getElementById('create-customer-btn');
    const placeOrderButton = document.querySelector('.place-order-button');

    // Search Customer
    if (searchCustomerButton) {
        searchCustomerButton.addEventListener('click', function () {
            const phoneNumber = document.getElementById('customer-phone').value.trim();
            justCreatedCustomer = false;

            if (phoneNumber.length === 10 && phoneNumber.startsWith('07')) {
                frappe.call({
                    method: 'custom_webshop.api.search_customer',
                    args: { phone_number: phoneNumber },
                    callback: function (response) {
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
                    }
                });
            } else {
                alert('Please enter a valid phone number (e.g., 07XXXXXXXX).');
            }
        });
    }

    // Create Customer
    if (createCustomerButton) {
        createCustomerButton.addEventListener('click', function () {
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
                            args: { phone: customer.mobile_no }
                        });

                        justCreatedCustomer = true;
                        const form = document.getElementById('create-customer-form');
                        if (form) form.style.display = 'none';
                        alert("Customer created successfully.");
                    } else {
                        alert(response.message.error || "Error creating customer.");
                    }
                }
            });
        });
    }

    // Place Order
    if (placeOrderButton) {
        placeOrderButton.addEventListener('click', function () {
            const phone = sessionStorage.getItem('customer_phone');
            if (!phone) {
                alert("Please search or create a customer before placing an order.");
                return;
            }
            frappe.call({
                method: 'custom_webshop.api.custom_place_order',
                args: { phone: phone },
                callback: function (response) {
                    if (!response.exc && response.message) {
                        window.location.href = `/orders/${response.message}`;
                    } else {
                        frappe.msgprint(__('Error placing order. Please try again.'));
                    }
                }
            });
        });
    }

    // Plus, Minus button binding
    $(".cart-items").on("click", ".cart-btn", function () {
        const $btn = $(this);
        const dir = $btn.data("dir");
        const input = $btn.closest(".number-spinner").find("input.cart-qty");
        let currentQty = parseFloat(input.val()) || 0;
        const itemCode = input.data("item-code");

        if (dir === "up") {
            currentQty += 1;
        } else if (dir === "dwn" && currentQty > 1) {
            currentQty -= 1;
        }

        shopping_cart.shopping_cart_update({ item_code: itemCode, qty: currentQty });
    });

    // Remove item
    $(".cart-items").on("click", ".remove-cart-item", function () {
        const itemCode = $(this).data("item-code");
        shopping_cart.shopping_cart_update({ item_code: itemCode, qty: 0 });
    });

    // Typing directly in quantity
    $(".cart-items").on("change blur", ".cart-qty", function () {
        const $input = $(this);
        const itemCode = $input.data("item-code");
        const newQty = parseFloat($input.val()) || 0;

        if (itemCode && newQty > 0) {
            shopping_cart.shopping_cart_update({ item_code: itemCode, qty: newQty });
        }
    });
});
