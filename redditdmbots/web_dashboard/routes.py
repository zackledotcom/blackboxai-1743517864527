from flask import request, jsonify
from . import app, socketio
from .bot import EvilRedditBot
from .reddit import load_config, save_config
import logging

# Initialize bot
bot = EvilRedditBot()

@app.route('/api/authenticate', methods=['POST'])
def authenticate():
    try:
        data = request.json
        if not all(k in data for k in ['username', 'password', 'client_id', 'client_secret']):
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
        
        config = load_config()
        config['reddit'].update(data)
        save_config(config)
        
        if bot.authenticate():
            return jsonify({'status': 'success', 'message': 'Authenticated'})
        return jsonify({'status': 'error', 'message': 'Authentication failed'}), 401
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/set-target', methods=['POST'])
def set_target():
    try:
        data = request.json
        if 'subreddit' not in data:
            return jsonify({'status': 'error', 'message': 'subreddit required'}), 400
        
        config = load_config()
        config['bots'][0]['subreddit'] = data['subreddit']
        save_config(config)
        
        return jsonify({'status': 'success', 'message': f'Target set to {data["subreddit"]}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/update-dnd', methods=['POST'])
def update_dnd():
    try:
        data = request.json
        if 'usernames' not in data:
            return jsonify({'status': 'error', 'message': 'usernames required'}), 400
        
        config = load_config()
        config['bots'][0]['protected_users'] = data['usernames']
        save_config(config)
        
        return jsonify({'status': 'success', 'message': f'Updated {len(data["usernames"])} protected users'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/status')
def status():
    try:
        return jsonify({
            'status': 'success',
            'data': {
                'isActive': bot.running,
                'messages': len(bot.activity_log),
                'subreddits': 1 if bot.current_subreddit else 0,
                'authenticated': bot.is_authenticated(),
                'subreddit': bot.current_subreddit,
                'protected_users': bot.protected_users
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/start', methods=['POST'])
def start_bot():
    try:
        if bot.running:
            return jsonify({'status': 'error', 'message': 'Bot is already running'}), 400
        
        success = bot.run()
        if success:
            return jsonify({'status': 'success', 'message': 'Bot started successfully'})
        return jsonify({'status': 'error', 'message': 'Failed to start bot'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    try:
        if not bot.running:
            return jsonify({'status': 'error', 'message': 'Bot is not running'}), 400
        
        bot.stop()
        return jsonify({'status': 'success', 'message': 'Bot stopped successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
