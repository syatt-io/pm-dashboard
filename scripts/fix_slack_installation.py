"""Fix Slack installation by inserting workspace record into database."""

import os
from datetime import datetime, timezone
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from src.models import SlackInstallation
from src.utils.database import get_engine
from sqlalchemy.orm import sessionmaker

# Get environment variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

if not SLACK_BOT_TOKEN:
    print("ERROR: SLACK_BOT_TOKEN not found in environment")
    exit(1)

# Initialize Slack client
client = WebClient(token=SLACK_BOT_TOKEN)

try:
    # Get workspace info
    auth_test = client.auth_test()
    team_id = auth_test["team_id"]
    team_name = auth_test["team"]
    bot_user_id = auth_test["user_id"]
    app_id = auth_test.get("app_id")

    print(f"Found workspace: {team_name} (ID: {team_id})")
    print(f"Bot user ID: {bot_user_id}")
    print(f"App ID: {app_id}")

    # Get bot scopes
    try:
        bot_info = client.bots_info(bot=bot_user_id)
        bot_scopes = ",".join(bot_info.get("bot", {}).get("app_scopes", []))
    except:
        bot_scopes = "unknown"

    # Insert/Update installation record in database
    engine = get_engine()
    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()
    try:
        # Check if installation already exists
        existing = session.query(SlackInstallation).filter_by(team_id=team_id).first()

        if existing:
            print(f"\nUpdating existing installation record...")
            existing.bot_token = SLACK_BOT_TOKEN
            existing.bot_user_id = bot_user_id
            existing.app_id = app_id
            existing.bot_scopes = bot_scopes
            existing.updated_at = datetime.now(timezone.utc)
            print("✅ Updated existing installation record")
        else:
            print(f"\nCreating new installation record...")
            installation = SlackInstallation(
                team_id=team_id,
                team_name=team_name,
                bot_token=SLACK_BOT_TOKEN,
                bot_user_id=bot_user_id,
                app_id=app_id,
                bot_scopes=bot_scopes,
                is_enterprise_install=False,
                installed_at=datetime.now(timezone.utc),
            )
            session.add(installation)
            print("✅ Created new installation record")

        session.commit()
        print(f"\nSlack installation record saved successfully!")
        print(f"Team: {team_name} ({team_id})")
        print(f"Bot User ID: {bot_user_id}")
        print(f"App ID: {app_id}")
        print(f"Scopes: {bot_scopes}")
    finally:
        session.close()

except SlackApiError as e:
    print(f"❌ Slack API error: {e.response['error']}")
    exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
    exit(1)
