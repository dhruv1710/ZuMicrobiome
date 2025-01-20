// Menu data loading and manipulation
async function loadMenuData(mealType) {
    try {
        const kitId = localStorage.getItem('kitId');
        const response = await fetch(`/get-menu-data?kitId=${kitId}&meal_type=${mealType}`);
        const data = await response.json();

        if (data.menu_data && data.menu_data[mealType]) {
            const contentDiv = document.getElementById(`${mealType}-content`);
            contentDiv.innerHTML = ''; // Clear existing content

            // Iterate through menu categories
            Object.entries(data.menu_data[mealType]).forEach(([category, items]) => {
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'category-section mb-3';

                // Create category header
                const header = document.createElement('div');
                header.className = 'category-header';
                header.innerHTML = `
                    <i data-feather="chevron-right" class="category-icon"></i>
                    <span>${category}</span>
                `;

                // Create items container
                const itemsDiv = document.createElement('div');
                itemsDiv.className = 'category-content';

                // Add items as checkboxes
                Object.keys(items).forEach(item => {
                    // Skip items that start with "No" or "NO"
                    if (!item.startsWith('No ') && !item.startsWith('NO ')) {
                        const itemDiv = document.createElement('div');
                        itemDiv.className = 'form-check';
                        itemDiv.innerHTML = `
                            <input class="form-check-input" type="checkbox" value="${item}" 
                                   id="${mealType}-${category}-${item.replace(/\s+/g, '-')}" />
                            <label class="form-check-label" for="${mealType}-${category}-${item.replace(/\s+/g, '-')}">
                                ${item}
                            </label>
                        `;
                        itemsDiv.appendChild(itemDiv);
                    }
                });

                categoryDiv.appendChild(header);
                categoryDiv.appendChild(itemsDiv);
                contentDiv.appendChild(categoryDiv);

                // Add click handler for category expansion
                header.addEventListener('click', () => {
                    const icon = header.querySelector('.category-icon');
                    icon.classList.toggle('expanded');
                    itemsDiv.classList.toggle('expanded');
                });
            });

            // Replace Feather icons
            feather.replace();
        } else {
            console.warn('No data available for the specified meal type');
        }
    } catch (error) {
        console.error('Error loading menu data:', error);
    }
}

// Save meal data
async function saveMealData(mealType) {
    const contentDiv = document.getElementById(`${mealType}-content`);
    const selectedFoods = {};

    // Get all categories
    const categories = contentDiv.querySelectorAll('.category-section');
    categories.forEach(category => {
        const categoryName = category.querySelector('.category-header span').textContent;
        const checkedItems = Array.from(category.querySelectorAll('input[type="checkbox"]:checked'))
            .map(checkbox => checkbox.value);

        if (checkedItems.length > 0) {
            selectedFoods[categoryName] = checkedItems;
        }
    });

    try {
        const kitId = localStorage.getItem('kitId');
        const response = await fetch('/save-meal', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                kitId: kitId,
                type: mealType,
                foods: selectedFoods
            })
        });

        const data = await response.json();
        if (data.success) {
            window.location.href = '/dashboard';
        } else {
            alert('Failed to save meal data');
        }
    } catch (error) {
        console.error('Error saving meal data:', error);
        alert('Failed to save meal data');
    }
}