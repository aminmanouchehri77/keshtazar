document.addEventListener('DOMContentLoaded', function() {
    const nameField = document.getElementById('id_name');
    const slugField = document.getElementById('id_slug');

    if (nameField && slugField) {
        nameField.addEventListener('input', function(e) {
            const nameValue = e.target.value;
            // تبدیل به اسلاگ فارسی با جایگزینی فاصله با خط تیره
            const slugValue = nameValue.replace(/\s+/g, '-');
            slugField.value = slugValue;
        });
    }
});