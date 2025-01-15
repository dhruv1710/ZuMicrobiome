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
    const steps = document.querySelectorAll('.form-step');
    const currentStepElement = document.getElementById(`step${currentStep}`);
    const nextStepElement = document.getElementById(`step${step}`);

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
    const icon = document.querySelector(`[onclick="toggleCategory('${categoryId}')"] .category-icon`);

    if (content) {
        content.classList.toggle('expanded');
        icon.classList.toggle('expanded');
    }
}


// Modified saveTracking function to handle hierarchical meal data and simplified mood
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
        mood: parseInt(document.getElementById('moodSlider').value)
    };

    // Save to database
    fetch('/save-tracking', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(trackingData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Redirect to insights page with new_submission parameter
            window.location.href = `/insights/${trackingData.kitId}?new_submission=true`;
        } else {
            alert('Failed to save data');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to save data');
    });
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
