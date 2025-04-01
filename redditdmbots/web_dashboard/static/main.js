// Initialize Socket.IO connection
const socket = io();

// DOM Elements
const activityFeed = document.getElementById('activity-feed');
const botForm = document.getElementById('bot-config');
const startButton = document.getElementById('start-bot');
const stopButton = document.getElementById('stop-bot');
const botStatus = document.querySelector('.bot-status');
const messagesCount = document.getElementById('messages-count');
const subredditsCount = document.getElementById('subreddits-count');

// Activity Feed Management
function addActivity(activity) {
    const activityElement = document.createElement('div');
    activityElement.className = `bg-[#272729] p-3 rounded border border-[#343536] ${activity.type === 'error' ? 'border-red-500' : ''}`;
    
    const timestamp = new Date().toLocaleTimeString();
    const icon = getActivityIcon(activity.type);
    
    activityElement.innerHTML = `
        <div class="flex items-center justify-between mb-1">
            <div class="flex items-center space-x-2">
                <i class="${icon} ${activity.type === 'error' ? 'text-red-500' : 'text-[#FF4500]'}"></i>
                <span class="text-sm font-medium">${activity.title}</span>
            </div>
            <span class="text-xs text-[#818384]">${timestamp}</span>
        </div>
        <p class="text-sm text-[#D7DADC] opacity-90">${activity.description}</p>
    `;
    
    activityFeed.prepend(activityElement);

    // Limit activity feed items
    while (activityFeed.children.length > 50) {
        activityFeed.removeChild(activityFeed.lastChild);
    }
}

function getActivityIcon(type) {
    const icons = {
        'auth': 'fa-solid fa-key',
        'comment': 'fa-regular fa-comment',
        'upvote': 'fa-solid fa-arrow-up',
        'error': 'fa-solid fa-triangle-exclamation',
        'start': 'fa-solid fa-play',
        'stop': 'fa-solid fa-stop',
        'target': 'fa-solid fa-crosshairs',
        'dnd': 'fa-solid fa-user-shield',
        'info': 'fa-solid fa-info-circle',
        'success': 'fa-solid fa-check-circle',
        'validation': 'fa-solid fa-exclamation-circle'
    };
    return icons[type] || 'fa-regular fa-circle';
}

// Form Validation
function validateForm(formData) {
    const requiredFields = ['subreddit', 'username', 'password', 'client_id', 'client_secret'];
    const missingFields = [];
    
    for (const field of requiredFields) {
        if (!formData.get(field)?.trim()) {
            missingFields.push(field);
            // Add error styling to the input
            const input = botForm.elements[field];
            input.classList.add('border-red-500');
            input.addEventListener('input', function() {
                this.classList.remove('border-red-500');
            }, { once: true });
        }
    }
    
    if (missingFields.length > 0) {
        addActivity({
            type: 'validation',
            title: 'Validation Error',
            description: `Please fill in all required fields: ${missingFields.join(', ')}`
        });
        return false;
    }
    
    return true;
}

// API Calls
async function makeRequest(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(endpoint, options);
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.message || 'Request failed');
        }

        if (result.log) {
            addActivity({
                type: endpoint.includes('start') ? 'start' : 
                      endpoint.includes('stop') ? 'stop' : 
                      endpoint.includes('auth') ? 'auth' : 'info',
                title: result.message,
                description: result.log
            });
        }

        return result;
    } catch (error) {
        addActivity({
            type: 'error',
            title: 'Request Failed',
            description: error.message
        });
        throw error;
    }
}

// Form Handling
botForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(botForm);
    
    // Validate form
    if (!validateForm(formData)) {
        return;
    }

    const botConfig = {
        subreddit: formData.get('subreddit').trim(),
        username: formData.get('username').trim(),
        password: formData.get('password').trim(),
        client_id: formData.get('client_id').trim(),
        client_secret: formData.get('client_secret').trim()
    };

    try {
        // First authenticate
        const authResult = await makeRequest('/api/authenticate', 'POST', botConfig);
        
        // Then set the target subreddit
        await makeRequest('/api/set-target', 'POST', { subreddit: botConfig.subreddit });
        
        // Clear sensitive form fields
        ['password', 'client_id', 'client_secret'].forEach(field => {
            botForm.elements[field].value = '';
        });

        // Update UI
        updateBotStatus(true);
        startButton.disabled = false;
        stopButton.disabled = true;

        addActivity({
            type: 'success',
            title: 'Bot Configured',
            description: `Bot configured successfully for r/${botConfig.subreddit}`
        });

    } catch (error) {
        updateBotStatus(false);
        addActivity({
            type: 'error',
            title: 'Configuration Failed',
            description: error.message
        });
    }
});

// Bot Controls
startButton.addEventListener('click', async () => {
    try {
        await makeRequest('/api/start', 'POST');
        updateBotStatus(true);
        startButton.disabled = true;
        stopButton.disabled = false;
        
        addActivity({
            type: 'start',
            title: 'Bot Started',
            description: 'Bot is now running and monitoring the target subreddit'
        });
    } catch (error) {
        updateBotStatus(false);
    }
});

stopButton.addEventListener('click', async () => {
    try {
        await makeRequest('/api/stop', 'POST');
        updateBotStatus(false);
        startButton.disabled = false;
        stopButton.disabled = true;
        
        addActivity({
            type: 'stop',
            title: 'Bot Stopped',
            description: 'Bot has been stopped successfully'
        });
    } catch (error) {
        // Keep current status if stop fails
        addActivity({
            type: 'error',
            title: 'Stop Failed',
            description: error.message
        });
    }
});

// Status Updates
function updateBotStatus(isActive) {
    const statusIcon = botStatus.querySelector('i');
    const statusText = botStatus.textContent;
    
    if (isActive) {
        statusIcon.className = 'fa-solid fa-circle text-green-500 mr-2';
        statusText.textContent = 'Active';
        botStatus.classList.remove('text-[#818384]');
        botStatus.classList.add('text-green-500');
    } else {
        statusIcon.className = 'fa-solid fa-circle text-gray-500 mr-2';
        statusText.textContent = 'Inactive';
        botStatus.classList.remove('text-green-500');
        botStatus.classList.add('text-[#818384]');
    }
}

// Socket.IO Event Handlers
socket.on('connect', () => {
    addActivity({
        type: 'success',
        title: 'Connected',
        description: 'Real-time updates enabled'
    });
});

socket.on('disconnect', () => {
    addActivity({
        type: 'error',
        title: 'Disconnected',
        description: 'Real-time updates disabled'
    });
});

socket.on('bot_update', (data) => {
    switch (data.type) {
        case 'auth_success':
            updateBotStatus(true);
            break;
        case 'bot_started':
            updateBotStatus(true);
            startButton.disabled = true;
            stopButton.disabled = false;
            break;
        case 'bot_stopped':
            updateBotStatus(false);
            startButton.disabled = false;
            stopButton.disabled = true;
            break;
        case 'error':
            addActivity({
                type: 'error',
                title: 'Bot Error',
                description: data.data.error
            });
            break;
    }
});

// Initial status check
(async () => {
    try {
        const status = await makeRequest('/api/status');
        if (status.data) {
            updateBotStatus(status.data.authenticated && status.data.running);
            messagesCount.textContent = status.data.messages || 0;
            subredditsCount.textContent = status.data.subreddits || 0;
        }
    } catch (error) {
        console.error('Initial status check failed:', error);
        addActivity({
            type: 'error',
            title: 'Status Check Failed',
            description: 'Could not retrieve initial bot status'
        });
    }
})();