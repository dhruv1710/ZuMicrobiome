// Global variables - moved to top
const totalSteps = 3;
let currentStep = 1;

// Form navigation functions
function showStep(step) {
    if (step < 1 || step > totalSteps) return;

    const currentStepElement = document.getElementById(`step${currentStep}`);
    const nextStepElement = document.getElementById(`step${step}`);

    if (!nextStepElement) return;

    // First hide the current step with animation
    if (currentStepElement) {
        currentStepElement.style.opacity = '0';
        currentStepElement.style.transform = 'translateX(-20px)';
        setTimeout(() => {
            currentStepElement.classList.add('d-none');

            // Then show the next step with animation
            nextStepElement.classList.remove('d-none');
            setTimeout(() => {
                nextStepElement.style.opacity = '1';
                nextStepElement.style.transform = 'translateX(0)';
            }, 50);
        }, 300);
    } else {
        // For the first step
        nextStepElement.classList.remove('d-none');
        nextStepElement.style.opacity = '1';
        nextStepElement.style.transform = 'translateX(0)';
    }

    currentStep = step;
}

function nextStep(currentStepNum) {
    if (currentStepNum < totalSteps) {
        showStep(currentStepNum + 1);
    }
}

function prevStep(currentStepNum) {
    if (currentStepNum > 1) {
        showStep(currentStepNum - 1);
    }
}

// Check if service worker is supported
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(registration => {
                console.log('ServiceWorker registration successful');
            })
            .catch(err => {
                console.log('ServiceWorker registration failed: ', err);
            });
    });
}

// Modified loadMenuData function for proper menu rendering
// async function loadMenuData(meal_type) {
//     const kitId = localStorage.getItem('kitId');
//     if (kitId && meal_type) {
//         try {
//             const response = await fetch(`/get-menu-data?kitId=${kitId}&meal_type=${meal_type}`);
//             const data = await response.json();
//             console.log('Menu data:', data);
//             if (data.menu_data) {
//                 const menuData = JSON.parse(data.menu_data);
//                 console.log(`meal data: ${JSON.stringify(menuData[meal_type])}`)
//                 // Function to create menu items for a meal type
//                 const createMenuItems = (mealType, categories) => {
//                     const mealSection = document.getElementById(`${mealType}-content`);
//                     console.log(`meal section: ${mealSection}`)
//                     console.log(`categories: ${categories}`)
//                     if (mealSection) {
//                         mealSection.innerHTML = ''; // Clear existing content
                        
//                         // Create categories
//                         Object.entries(categories).forEach(([category, items]) => {
//                             const categoryDiv = document.createElement('div');
//                             categoryDiv.className = 'meal-category mb-3';

//                             const categoryContent = `
//                                 <div class="category-header" onclick="toggleCategory('${mealType}-${category}')">
//                                     <h5>
//                                         <i data-feather="chevron-right" class="category-icon"></i>
//                                         ${category.charAt(0).toUpperCase() + category.slice(1)}
//                                     </h5>
//                                 </div>
//                                 <div class="category-content" id="${mealType}-${category}-content">
//                                     ${Object.keys(items).map(item => `
//                                         <div class="form-check">
//                                             <input class="form-check-input" type="checkbox" 
//                                                 id="${mealType}-${category}-${item}"
//                                                 name="${mealType}-${category}-${item}">
//                                             <label class="form-check-label" 
//                                                 for="${mealType}-${category}-${item}">
//                                                 ${item}
//                                             </label>
//                                         </div>
//                                     `).join('')}
//                                 </div>
//                             `;

//                             categoryDiv.innerHTML = categoryContent;
//                             mealSection.appendChild(categoryDiv);
//                         });

//                         // Initialize Feather icons
//                         feather.replace();
//                     }
//                 };

//                 // Create menu sections for each meal type
//                 [meal_type].forEach(mealType => {
//                     if (menuData[mealType]) {
//                         createMenuItems(mealType, menuData[mealType]);
//                     }
//                 });
//             } else {
//                 console.error('No menu data available:', data.error);
//             }
//         } catch (error) {
//             console.error('Error loading menu data:', error);
//         }
//     } else {
//         console.error('No kit ID or meal type found in localStorage');
//     }
// }

// Handle category expansion
function toggleCategory(categoryId) {
    const content = document.getElementById(`${categoryId}-content`);
    const icon = document.querySelector(`[onclick="toggleCategory('${categoryId}')"] .category-icon`);

    if (content && icon) {
        content.classList.toggle('expanded');
        icon.classList.toggle('rotated');
    }
}

// Get meal data helper function
function getMealData(mealType) {
    const foods = {};
    const mealSection = document.getElementById(`${mealType}-content`);
    if (mealSection) {
        // Get all categories in this meal section
        const categories = mealSection.getElementsByClassName('meal-category');
        Array.from(categories).forEach(category => {
            const categoryName = category.querySelector('.category-header h5').textContent.trim();
            foods[categoryName] = [];

            // Get checked items in this category
            const checkedItems = category.querySelectorAll('input[type="checkbox"]:checked');
            checkedItems.forEach(item => {
                const itemName = item.nextElementSibling.textContent.trim();
                foods[categoryName].push(itemName);
            });

            // Remove empty categories
            if (foods[categoryName].length === 0) {
                delete foods[categoryName];
            }
        });
    }
    return foods;
}

// Async submission functions for each section
// async function saveMealData(mealType) {
//     const mealData = {
//         date: new Date().toISOString(),
//         kitId: localStorage.getItem('kitId'),
//         type: mealType,
//         foods: getMealData(mealType)
//     };

//     try {
//         const response = await fetch('/save-meal', {
//             method: 'POST',
//             headers: {
//                 'Content-Type': 'application/json',
//             },
//             body: JSON.stringify(mealData)
//         });

//         const result = await response.json();
//         if (result.success) {
//             alert(`${mealType.charAt(0).toUpperCase() + mealType.slice(1)} data saved successfully!`);
//             window.location.href = '/';
//         } else {
//             alert('Failed to save meal data');
//         }
//     } catch (error) {
//         console.error('Error:', error);
//         alert('Failed to save meal data');
//     }
// }

async function saveStoolData() {
    const stoolData = {
        date: new Date().toISOString(),
        kitId: localStorage.getItem('kitId'),
        type: document.querySelector('input[name="stoolType"]:checked')?.value,
        relief: parseInt(document.getElementById('reliefSlider')?.value || 3),
        smell: parseInt(document.getElementById('smellSlider')?.value || 3)
    };

    try {
        const response = await fetch('/save-stool', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(stoolData)
        });

        const result = await response.json();
        if (result.success) {
            alert('Stool data saved successfully!');
            window.location.href = '/';
        } else {
            alert('Failed to save stool data');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to save stool data');
    }
}

async function saveMoodData() {
    // Check if mood was already submitted today
    if (localStorage.getItem('moodSubmittedDate') === new Date().toISOString().split('T')[0]) {
        alert('Mood already submitted for today');
        return;
    }

    const moodData = {
        date: new Date().toISOString(),
        kitId: localStorage.getItem('kitId'),
        mood: {
            morning_mood: parseInt(document.querySelector('input[name="morning_mood"]:checked')?.value || 0),
            meal_mood: parseInt(document.querySelector('input[name="meal_mood"]:checked')?.value || 0),
            energy_level: parseInt(document.getElementById('energySlider')?.value || 3),
            evening_mood: parseInt(document.querySelector('input[name="evening_mood"]:checked')?.value || 0),
            overall_mood: parseInt(document.getElementById('overallMoodSlider')?.value || 3)
        }
    };

    try {
        const response = await fetch('/save-mood', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(moodData)
        });

        const result = await response.json();
        if (result.success) {
            // Store submission date
            localStorage.setItem('moodSubmittedDate', new Date().toISOString().split('T')[0]);
            alert('Mood data saved successfully!');
            window.location.href = '/';
        } else {
            alert('Failed to save mood data');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to save mood data');
    }
}

// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Load menu data -  Call loadMenuData with meal type parameter
    loadMenuData('breakfast'); // Example: Load breakfast menu data.  Adjust 'breakfast' as needed.

    // Replace Feather icons
    feather.replace();

    // Show all sections initially
    document.querySelectorAll('.form-step').forEach(step => {
        step.classList.remove('d-none');
        step.style.opacity = '1';
        step.style.transform = 'translateX(0)';
    });
});

// Array of preset colors (remove duplicate declaration)
const stoolColors = ['#8B4513', '#FFD700', '#228B22', '#FF0000', '#FFFFFF', '#000000'];


// Initialize charts only if they exist on the page
document.addEventListener('DOMContentLoaded', function() {
    const moodChartCanvas = document.getElementById('moodChart');
    if (moodChartCanvas) {
        const ctx = moodChartCanvas.getContext('2d');
        window.moodChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Mood Level',
                    data: [],
                    borderColor: '#4CAF50',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 7
                    }
                }
            }
        });
    }
});