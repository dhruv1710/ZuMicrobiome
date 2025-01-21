// Menu data loading and manipulation
async function loadMenuData(mealType) {
    try {
        const kitId = localStorage.getItem('kitId');
        const response = await fetch(`/get-menu-data?kitId=${kitId}&meal_type=${mealType}`);
        const data = await response.json();
        parsed = JSON.parse(data.menu_data)[mealType];
        if (parsed) {
            const contentDiv = document.getElementById(`${mealType}-content`);
            if (!contentDiv) {
                console.error(`Content div for ${mealType} not found`);
                return;
            }
            contentDiv.innerHTML = ''; // Clear existing content

            // Iterate through menu categories
            Object.entries(parsed).forEach(([category, items]) => {
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
    if (!contentDiv) {
        console.error('Content div not found');
        return;
    }

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

    // Validate if any foods were selected
    if (Object.keys(selectedFoods).length === 0) {
        alert('Please select at least one food item');
        return;
    }

    try {
        const kitId = localStorage.getItem('kitId');
        if (!kitId) {
            console.error('Kit ID not found');
            return;
        }

        // Disable the submit button and show loading state
        const submitButton = document.querySelector(`button[onclick="saveMealData('${mealType}')"]`);
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = 'Saving...';
        }

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
            // Redirect to dashboard to ensure proper state update
            window.location.href = '/dashboard';
        } else {
            console.error('Failed to save meal data:', data.error);
            alert(data.error || 'Failed to save meal data');

            // Re-enable button on error
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = `Add ${mealType.charAt(0).toUpperCase() + mealType.slice(1)} Entry`;
            }
        }
    } catch (error) {
        console.error('Error saving meal data:', error);
        alert('Failed to save meal data');

        // Re-enable button on error
        const submitButton = document.querySelector(`button[onclick="saveMealData('${mealType}')"]`);
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = `Add ${mealType.charAt(0).toUpperCase() + mealType.slice(1)} Entry`;
        }
    }
}