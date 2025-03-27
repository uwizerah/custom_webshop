document.getElementById('search-customer').addEventListener('click', function() {
    const phoneNumber = document.getElementById('customer-phone').value.trim();

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
                } else {
                    document.getElementById('customer-name').innerText = "Not Found";
                    document.getElementById('customer-phone-display').innerText = "";
                }
            },
            error: function(err) {
                console.error("❌ Frappe call failed:", err);
            }
        });
    } else {
        console.warn("❗ Invalid phone number format.");
        alert('Please enter a valid phone number (e.g., 07XXXXXXXX).');
    }
});