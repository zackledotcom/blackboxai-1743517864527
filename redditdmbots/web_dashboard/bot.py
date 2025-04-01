import praw
import time
import logging
from datetime import datetime

class EvilRedditBot:
    def __init__(self):
        self.config = {
            'reddit': {},
            'bots': [{
                'subreddit': '',
                'protected_users': [],
                'actions': {
                    'upvote': True,
                    'comment': True,
                    'response_message': ''
                }
            }]
        }
        self.running = False
        self.reddit = None
        self.current_subreddit = None
        self.protected_users = []
        self.activity_log = []
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs.txt'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('RedditBot')

    def authenticate(self):
        """Authenticate with Reddit using PRAW"""
        try:
            if not all(key in self.config['reddit'] for key in ['username', 'password', 'client_id', 'client_secret', 'user_agent']):
                self.logger.error("Missing required Reddit credentials")
                return False

            self.reddit = praw.Reddit(
                username=self.config['reddit']['username'],
                password=self.config['reddit']['password'],
                client_id=self.config['reddit']['client_id'],
                client_secret=self.config['reddit']['client_secret'],
                user_agent=self.config['reddit']['user_agent']
            )
            self.logger.info(f"Authenticated as {self.config['reddit']['username']}")
            return True
        except Exception as e:
            self.logger.error(f"Authentication failed: {str(e)}")
            return False

    def is_authenticated(self):
        """Check if the bot is authenticated with Reddit"""
        return self.reddit is not None and hasattr(self.reddit, 'user') and self.reddit.user.me() is not None

    def process_submission(self, submission):
        """Process a single Reddit submission"""
        try:
            if not submission.author:
                self.logger.warning(f"Skipping submission {submission.id} - no author")
                return

            if submission.author.name in self.protected_users:
                self.logger.info(f"Skipping protected user: {submission.author.name}")
                return

            actions = self.config['bots'][0]['actions']
            
            if actions.get('upvote', True):
                submission.upvote()
                self.logger.info(f"Upvoted submission: {submission.id} by {submission.author.name}")
            
            if actions.get('comment', True) and actions.get('response_message'):
                submission.reply(actions['response_message'])
                self.logger.info(f"Commented on submission: {submission.id}")
                
            # Add to activity log
            self.activity_log.append({
                'timestamp': datetime.now().isoformat(),
                'action': 'process_submission',
                'submission_id': submission.id,
                'author': submission.author.name,
                'success': True
            })
            
        except Exception as e:
            self.logger.error(f"Error processing submission {submission.id}: {str(e)}")
            self.activity_log.append({
                'timestamp': datetime.now().isoformat(),
                'action': 'process_submission',
                'submission_id': submission.id,
                'error': str(e),
                'success': False
            })

    def run(self):
        """Main bot loop"""
        if not self.authenticate():
            self.logger.error("Failed to authenticate. Bot cannot start.")
            return False

        self.running = True
        self.current_subreddit = self.config['bots'][0]['subreddit']
        self.protected_users = self.config['bots'][0].get('protected_users', [])
        
        self.logger.info(f"Bot started monitoring r/{self.current_subreddit}")
        
        while self.running:
            try:
                if not self.current_subreddit:
                    self.logger.warning("No subreddit specified. Waiting...")
                    time.sleep(60)
                    continue

                subreddit = self.reddit.subreddit(self.current_subreddit)
                for submission in subreddit.new(limit=5):
                    if not self.running:
                        break
                    self.process_submission(submission)
                
                time.sleep(60)  # Wait before next batch
                
            except praw.exceptions.PRAWException as e:
                self.logger.error(f"PRAW error: {str(e)}")
                time.sleep(300)  # Wait longer on PRAW errors
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}")
                if not self.running:  # Don't sleep if we're stopping
                    break
                time.sleep(60)

        self.logger.info("Bot stopped")
        return True

    def stop(self):
        """Stop the bot gracefully"""
        self.logger.info("Stopping bot...")
        self.running = False
        
    def get_status(self):
        """Get current bot status"""
        return {
            'running': self.running,
            'authenticated': self.is_authenticated(),
            'current_subreddit': self.current_subreddit,
            'protected_users_count': len(self.protected_users),
            'activity_log_count': len(self.activity_log)
        }