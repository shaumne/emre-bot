"""
Quick setup script for Polymarket Arbitrage Bot.
Creates .env file and logs directory.
"""

import os
import shutil


def setup_environment():
    """Setup environment for the bot."""
    print("=" * 60)
    print("POLYMARKET ARBITRAGE BOT - SETUP")
    print("=" * 60)
    print()
    
    # Create .env file from template
    if os.path.exists(".env"):
        print("✓ .env file already exists")
    else:
        if os.path.exists("env_template.txt"):
            shutil.copy("env_template.txt", ".env")
            print("✓ Created .env file from template")
            print("  → Please edit .env and add your credentials!")
        else:
            print("✗ env_template.txt not found!")
            return False
    
    # Create logs directory
    if not os.path.exists("logs"):
        os.makedirs("logs")
        print("✓ Created logs/ directory")
    else:
        print("✓ logs/ directory already exists")
    
    print()
    print("=" * 60)
    print("SETUP COMPLETE!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Edit .env file and add your Polymarket credentials")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Run the bot: python bot.py")
    print()
    
    return True


if __name__ == "__main__":
    setup_environment()


