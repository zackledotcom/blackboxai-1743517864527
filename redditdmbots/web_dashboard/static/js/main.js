// Activity Feed Management
class ActivityFeed {
    constructor() {
        this.feed = document.getElementById('activity-feed');
        this.activities = [];
    }

    addActivity(activity) {
        const activityElement = this.createActivityElement(activity);
        this.feed.insertBefore(activityElement, this.feed.firstChild);
        this.activities.push(activity);
        
        // Update counters
        this.updateCounters();
    }

    createActivityElement(activity) {
        const div = document.createElement('div');
        div.className = 'feed-item';
        
        const timestamp = new Date(activity.timestamp).toLocaleTimeString();
        const icon = this.getActivityIcon(activity.type);
        
        div.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center space-x-2">
                    <i class="${icon} text-[#FF4500]"></i>
                    <span class="text-sm font-medium">${activity.title}</span>
                </div>
                <span class="text-xs text-[#818384]">${timestamp}</span>
            </div>
            <p class="text-sm text-[#D7DADC] opacity-90">${activity.description}</p>
            ${activity.subreddit ? `
                <div class="mt-2 flex items-center space-x-1 text-xs text-[#818384]">
                    <i class="fa-regular fa-compass"></i>
                    <span>r/${activity.subreddit}</span>
                </div>
            ` : ''}
        `;
        
        return div;
    }

    getActivityIcon(type) {
        const icons = {
            'comment': 'fa-regular fa-comment',
            'upvote': 'fa-solid fa-arrow-up',
            'auth': 'fa-solid fa-key',
            'target': 'fa-solid fa-crosshairs',
            'error': 'fa-solid fa-triangle-exclamation'
        };
        return icons[type] || 'fa-regular fa-circle';
    }

    updateCounters() {
        const messageCount = this.activities.filter(a => a.type === 'comment').length;
        const subredditCount = new Set(this.activities.filter(a => a.subreddit).map(a => a.subreddit)).size;
        
        document.getElementById('messages-count').textContent = messageCount;
        document.getElementById('subreddits-count').textContent = subredditCount;
    }
}

// Form Handling
class BotForm {
    constructor(formElement, activityFeed) {
        this.form = formElement;
        this.activityFeed = activityFeed;
        this.setupEventListeners();
    }

    setupEventListeners() {
        this.form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleSubmit();
        });
    }

    async handleSubmit() {
        const formData = new FormData(this.form);
        const botData = {
            subreddit: formData.get('subreddit'),
            protected_users: formData.get('protected_users').split('\n').filter(u => u.trim()),
            response_style: formData.get('response_style'),
            writing_style: formData.get('writing_style'),
            response_length: formData.get('response_length'),
            traits: Array.from(formData.getAll('traits')),
            triggers: formData.get('triggers').split(',').map(t => t.trim()),
            auth: {
                username: formData.get('username'),
                password: formData.get('password'),
                client_id: formData.get('client_id'),
                client_secret: formData.get('client_secret')
            }
        };

        try {
            // First authenticate
            const authResponse = await fetch('/api/authenticate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(botData.auth)
            });
            const authResult = await authResponse.json();
            
            if (authResult.status === 'success') {
                this.activityFeed.addActivity({
                    type: 'auth',
                    title: 'Authentication Successful',
                    description: authResult.message,
                    timestamp: new Date()
                });

                // Then set target
                const targetResponse = await fetch('/api/set-target', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ subreddit: botData.subreddit })
                });
                const targetResult = await targetResponse.json();
                
                if (targetResult.status === 'success') {
                    this.activityFeed.addActivity({
                        type: 'target',
                        title: 'Target Set',
                        description: targetResult.message,
                        subreddit: botData.subreddit,
                        timestamp: new Date()
                    });

                    // Finally update protected users
                    const dndResponse = await fetch('/api/update-dnd', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ usernames: botData.protected_users })
                    });
                    const dndResult = await dndResponse.json();
                    
                    if (dndResult.status === 'success') {
                        this.activityFeed.addActivity({
                            type: 'shield',
                            title: 'Protected Users Updated',
                            description: dndResult.message,
                            timestamp: new Date()
                        });
                    }
                }
            }
        } catch (error) {
            this.activityFeed.addActivity({
                type: 'error',
                title: 'Error',
                description: 'Failed to initialize bot: ' + error.message,
                timestamp: new Date()
            });
        }
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const activityFeed = new ActivityFeed();
    
    // Initialize forms
    document.querySelectorAll('form[id^="bot"]').forEach(form => {
        new BotForm(form, activityFeed);
    });

    // Poll for status updates
    setInterval(async () => {
        try {
            const response = await fetch('/api/status');
            const status = await response.json();
            
            if (status.data.authenticated) {
                document.querySelectorAll('.bot-status').forEach(el => {
                    el.innerHTML = `<i class="fa-solid fa-circle text-green-500 mr-2"></i>Active`;
                });
            }
        } catch (error) {
            console.error('Failed to fetch status:', error);
        }
    }, 5000);
});