from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import os
import json
import logging
from datetime import datetime
import threading
import sys
sys.path.append('..')
from bot import EvilRedditBot

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Store bot instances
bots = {}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('web_dashboard')

# Load config
def load_config():
    config_path = 'config/config.json'
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        default_config = {
            "reddit": {},
            "subreddits": [],
            "bot_actions": {
                "upvote": True,
                "comment": True,
                "response_message": ""
            },
            "ui": {
                "do_not_disturb": []
            }
        }
        os.makedirs('config', exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
        logger.info("Created default configuration file")
        return default_config
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        raise

# Save config
def save_config(config):
    try:
        os.makedirs('config', exist_ok=True)
        with open('config/config.json', 'w') as f:
            json.dump(config, f, indent=4)
        logger.info("Configuration saved successfully")
    except Exception as e:
        logger.error(f"Error saving config: {str(e)}")
        raise

# Evil logger
def log_action(action, status="SUCCESS", details=""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {action} - {status}: {details}"
    logger.info(log_entry)
    return log_entry

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/authenticate', methods=['POST'])
def authenticate():
    try:
        data = request.get_json()
        
        # Create new bot instance
        bot = EvilRedditBot()
        bot.config['reddit'] = {
            'username': data['username'],
            'password': data['password'],
            'client_id': data['client_id'],
            'client_secret': data['client_secret'],
            'user_agent': 'EvilRedditBot/1.0'
        }
        
        # Try to authenticate
        if not bot.authenticate():
            return jsonify({
                'status': 'error',
                'message': 'Authentication failed',
                'log': log_action("Authentication", "ERROR", f"Failed for user {data['username']}")
            }), 401

        # Store bot instance
        bot_id = f"bot_{data['username']}"
        bots[bot_id] = bot
        session['bot_id'] = bot_id
        session['username'] = data['username']

        # Save config
        config = load_config()
        config['reddit'] = bot.config['reddit']
        save_config(config)

        # Emit socket event
        socketio.emit('bot_update', {
            'type': 'auth_success',
            'data': {'username': data['username']}
        })

        return jsonify({
            'status': 'success',
            'message': 'Authentication successful',
            'log': log_action("Authentication", "SUCCESS", f"Authenticated as {data['username']}")
        })

    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'log': log_action("Authentication", "ERROR", str(e))
        }), 500

@app.route('/api/set-target', methods=['POST'])
def set_target():
    try:
        data = request.get_json()
        bot_id = session.get('bot_id')
        
        if not bot_id or bot_id not in bots:
            return jsonify({
                'status': 'error',
                'message': 'Not authenticated',
                'log': log_action("Set Target", "ERROR", "Authentication required")
            }), 401

        bot = bots[bot_id]
        bot.config['bots'][0]['subreddit'] = data['subreddit']
        
        # Save config
        config = load_config()
        config['subreddits'] = [data['subreddit']]
        save_config(config)

        return jsonify({
            'status': 'success',
            'message': 'Target subreddit set',
            'log': log_action("Set Target", "SUCCESS", f"Set target to r/{data['subreddit']}")
        })

    except Exception as e:
        logger.error(f"Set target error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'log': log_action("Set Target", "ERROR", str(e))
        }), 500

@app.route('/api/start', methods=['POST'])
def start_bot():
    try:
        bot_id = session.get('bot_id')
        if not bot_id:
            return jsonify({
                'status': 'error',
                'message': 'Not authenticated',
                'log': log_action("Start Bot", "ERROR", "Authentication required")
            }), 401

        if bot_id not in bots:
            return jsonify({
                'status': 'error',
                'message': 'Bot instance not found',
                'log': log_action("Start Bot", "ERROR", "Bot instance not found")
            }), 404

        bot = bots[bot_id]
        if bot.running:
            return jsonify({
                'status': 'error',
                'message': 'Bot is already running',
                'log': log_action("Start Bot", "ERROR", "Bot already active")
            }), 400

        # Start bot in a separate thread
        def run_bot():
            try:
                bot.run()
            except Exception as e:
                logger.error(f"Bot error: {str(e)}")
                socketio.emit('bot_update', {
                    'type': 'error',
                    'data': {'error': str(e)}
                })

        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()

        # Emit update via WebSocket
        socketio.emit('bot_update', {
            'type': 'bot_started',
            'data': {'username': session['username']}
        })

        return jsonify({
            'status': 'success',
            'message': 'Bot started successfully',
            'log': log_action("Start Bot", "SUCCESS", f"Bot started for {session['username']}")
        })

    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'log': log_action("Start Bot", "ERROR", str(e))
        }), 500

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    try:
        bot_id = session.get('bot_id')
        if not bot_id or bot_id not in bots:
            return jsonify({
                'status': 'error',
                'message': 'Not authenticated',
                'log': log_action("Stop Bot", "ERROR", "Authentication required")
            }), 401

        bot = bots[bot_id]
        bot.stop()

        # Emit update via WebSocket
        socketio.emit('bot_update', {
            'type': 'bot_stopped',
            'data': {'username': session['username']}
        })

        return jsonify({
            'status': 'success',
            'message': 'Bot stopped successfully',
            'log': log_action("Stop Bot", "SUCCESS", f"Bot stopped for {session['username']}")
        })

    except Exception as e:
        logger.error(f"Error stopping bot: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'log': log_action("Stop Bot", "ERROR", str(e))
        }), 500

@app.route('/api/status')
def get_status():
    try:
        bot_id = session.get('bot_id')
        if not bot_id or bot_id not in bots:
            return jsonify({
                'status': 'success',
                'data': {
                    'authenticated': False,
                    'running': False,
                    'messages': 0,
                    'subreddits': 0
                }
            })

        bot = bots[bot_id]
        status = bot.get_status()
        
        return jsonify({
            'status': 'success',
            'data': {
                'authenticated': status['authenticated'],
                'running': status['running'],
                'messages': len(status.get('activity_log', [])),
                'subreddits': 1 if status.get('current_subreddit') else 0
            }
        })

    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    logger.error(f"404 error: {str(error)}")
    return jsonify({
        'status': 'error',
        'message': 'Resource not found',
        'log': log_action("Not Found", "ERROR", str(error))
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {str(error)}")
    return jsonify({
        'status': 'error',
        'message': 'An internal error occurred',
        'log': log_action("Internal Error", "ERROR", str(error))
    }), 500

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")
    bot_id = session.get('bot_id')
    if bot_id and bot_id in bots:
        emit('bot_update', {
            'type': 'status',
            'data': {
                'active': bots[bot_id].running,
                'username': bots[bot_id].config['reddit'].get('username')
            }
        })

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")

if __name__ == '__main__':
    # Load initial config
    load_config()
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)
