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

// Save tracking data
function saveTracking() {
    const trackingData = {
        date: new Date().toISOString(),
        kitId: localStorage.getItem('kitId'),
        meals: {
            breakfast: document.getElementById('breakfast1').checked,
            // Add other meal tracking
        },
        stool: {
            shape: document.getElementById('stoolShape').value,
            color: document.getElementById('stoolColor').value,
            // Add other stool characteristics
        },
        mood: document.getElementById('moodRange').value
    };

    // Save to localStorage
    const existingData = JSON.parse(localStorage.getItem('healthData') || '[]');
    existingData.push(trackingData);
    localStorage.setItem('healthData', JSON.stringify(existingData));

    alert('Data saved successfully!');
}
