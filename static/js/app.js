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

// Voice recognition setup
let recognition = null;
if ('webkitSpeechRecognition' in window) {
    recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
} else {
    console.log('Speech recognition not supported');
}

// Voice recording state
let isRecording = false;
let currentMode = null;

// Start voice recording
function startVoiceRecording(mode) {
    if (!recognition) {
        alert('Speech recognition is not supported in your browser');
        return;
    }

    if (isRecording) {
        stopVoiceRecording();
        return;
    }

    currentMode = mode;
    const outputDiv = document.getElementById(`${mode}VoiceOutput`);
    const button = document.getElementById(`${mode}VoiceBtn`);

    outputDiv.classList.remove('d-none');
    button.classList.add('btn-danger');
    button.innerHTML = '<i data-feather="mic-off"></i> Stop Recording';
    feather.replace();

    recognition.onresult = handleVoiceResult;
    recognition.onend = () => stopVoiceRecording();

    recognition.start();
    isRecording = true;
}

// Stop voice recording
function stopVoiceRecording() {
    if (!currentMode) return;

    const outputDiv = document.getElementById(`${currentMode}VoiceOutput`);
    const button = document.getElementById(`${currentMode}VoiceBtn`);

    outputDiv.classList.add('d-none');
    button.classList.remove('btn-danger');
    button.innerHTML = '<i data-feather="mic"></i> Record ' + currentMode.charAt(0).toUpperCase() + currentMode.slice(1);
    feather.replace();

    recognition.stop();
    isRecording = false;
}

// Handle voice recognition results
function handleVoiceResult(event) {
    const result = event.results[0][0].transcript.toLowerCase();
    console.log('Voice Input:', result);

    if (currentMode === 'meal') {
        handleMealVoiceCommand(result);
    } else if (currentMode === 'mood') {
        handleMoodVoiceCommand(result);
    }
}

// Process meal-related voice commands
function handleMealVoiceCommand(command) {
    const mealVoiceOutput = document.getElementById('mealVoiceOutput');
    mealVoiceOutput.innerHTML = `<p class="mb-0">Recognized: "${command}"</p>`;

    // Check for meal types
    if (command.includes('breakfast')) {
        document.getElementById('breakfast1').checked = true;
    }
    // Add more meal recognition logic here
}

// Process mood-related voice commands
function handleMoodVoiceCommand(command) {
    const moodVoiceOutput = document.getElementById('moodVoiceOutput');
    moodVoiceOutput.innerHTML = `<p class="mb-0">Recognized: "${command}"</p>`;

    // Map mood keywords to values
    const moodMap = {
        'terrible': 1,
        'bad': 2,
        'okay': 3,
        'good': 4,
        'great': 5,
        'amazing': 5
    };

    // Set mood value based on recognized keywords
    for (const [keyword, value] of Object.entries(moodMap)) {
        if (command.includes(keyword)) {
            document.getElementById('moodRange').value = value;
            break;
        }
    }
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