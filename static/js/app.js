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

// Form navigation functions
let currentStep = 1;
const totalSteps = 3;

function updateProgress() {
    const progress = ((currentStep - 1) / (totalSteps - 1)) * 100;
    document.getElementById('formProgress').style.width = `${progress}%`;
}

function showStep(step) {
    document.querySelectorAll('.form-step').forEach(el => {
        el.classList.add('d-none');
    });
    document.getElementById(`step${step}`).classList.remove('d-none');
    currentStep = step;
    updateProgress();
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

// New function to toggle category expansion
function toggleCategory(categoryId) {
    const content = document.getElementById(`${categoryId}-content`);
    const icon = content.previousElementSibling.querySelector('.category-icon');

    content.classList.toggle('expanded');
    icon.classList.toggle('expanded');
}

// Modified save tracking function to handle hierarchical meal data
function saveTracking() {
    const getMealData = (mealType) => {
        const foods = {};
        document.querySelectorAll(`#${mealType}-content input[type="checkbox"]`).forEach(checkbox => {
            const category = checkbox.id.split('-')[1];
            const food = checkbox.id.split('-')[2];

            if (!foods[category]) {
                foods[category] = [];
            }

            if (checkbox.checked) {
                foods[category].push(food);
            }
        });
        return foods;
    };

    const trackingData = {
        date: new Date().toISOString(),
        kitId: localStorage.getItem('kitId'),
        meals: {
            breakfast: getMealData('breakfast'),
            lunch: getMealData('lunch'),
            dinner: getMealData('dinner')
        },
        stool: {
            type: document.querySelector('input[name="stoolType"]:checked')?.value
        },
        mood: document.getElementById('moodRange').value
    };

    // Save to localStorage
    const existingData = JSON.parse(localStorage.getItem('healthData') || '[]');
    existingData.push(trackingData);
    localStorage.setItem('healthData', JSON.stringify(existingData));

    alert('Data saved successfully!');
    window.location.href = '/';
}

// Kit ID validation
function validateKitId() {
    const kitId = document.getElementById('kitId').value;

    if (!kitId) {
        alert('Please enter a Kit ID');
        return;
    }

    fetch(`/validate-kit/${kitId}`)
        .then(response => response.json())
        .then(data => {
            if (data.valid) {
                localStorage.setItem('kitId', kitId);
                window.location.href = '/track';
            } else {
                alert('Invalid Kit ID');
            }
        });
}


// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('formProgress')) {
        updateProgress();
    }

    // Replace Feather icons
    feather.replace();

    // Expand first category by default in each step
    document.querySelectorAll('.category-header').forEach(header => {
        if (header.querySelector('h4')) {  // Only top-level categories
            toggleCategory(header.textContent.trim().toLowerCase());
        }
    });
});