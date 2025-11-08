"""
Find IDs for all Tempo users who have logged time.
Generates a CSV with Google ID, Slack ID, Jira Account ID for bulk import.
"""

import os
import sys
import csv
import logging
import requests
from datetime import datetime, timedelta, date
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.tempo import TempoAPIClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class TempoUserIDFinder:
    """Find all IDs for Tempo users."""

    def __init__(self):
        self.tempo_client = TempoAPIClient()
        self.jira_url = os.getenv("JIRA_URL")
        self.jira_username = os.getenv("JIRA_USERNAME")
        self.jira_api_token = os.getenv("JIRA_API_TOKEN")
        self.jira_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def get_tempo_users_from_last_month(self):
        """Get all users who logged time in the last month."""
        logger.info("Fetching worklogs from last 30 days...")

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        worklogs = self.tempo_client.get_worklogs(
            from_date=start_date.isoformat(),
            to_date=end_date.isoformat()
        )

        logger.info(f"Found {len(worklogs)} worklogs")

        # Extract unique account IDs
        account_ids = set()
        for worklog in worklogs:
            author = worklog.get("author", {})
            account_id = author.get("accountId")
            if account_id:
                account_ids.add(account_id)

        logger.info(f"Found {len(account_ids)} unique Tempo users\n")
        return list(account_ids)

    def get_jira_user_info(self, account_id):
        """Get user information from Jira API."""
        try:
            url = f"{self.jira_url}/rest/api/3/user"
            params = {"accountId": account_id}

            response = requests.get(
                url,
                headers=self.jira_headers,
                params=params,
                auth=(self.jira_username, self.jira_api_token),
                timeout=10
            )
            response.raise_for_status()

            user_data = response.json()
            return {
                "account_id": account_id,
                "email": user_data.get("emailAddress", ""),
                "display_name": user_data.get("displayName", ""),
                "active": user_data.get("active", False)
            }
        except Exception as e:
            logger.warning(f"Error fetching user {account_id}: {e}")
            return {
                "account_id": account_id,
                "email": "",
                "display_name": "Unknown",
                "active": False
            }

    def find_slack_user_id(self, email):
        """Try to find Slack user ID by email (if Slack token available)."""
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        if not slack_token:
            return ""

        try:
            url = "https://slack.com/api/users.lookupByEmail"
            headers = {"Authorization": f"Bearer {slack_token}"}
            params = {"email": email}

            response = requests.get(url, headers=headers, params=params, timeout=10)
            data = response.json()

            if data.get("ok"):
                return data.get("user", {}).get("id", "")
        except Exception as e:
            logger.debug(f"Slack lookup failed for {email}: {e}")

        return ""

    def generate_csv(self, users_data, output_file="tempo_users.csv"):
        """Generate CSV file with user data."""
        logger.info(f"\nGenerating CSV: {output_file}\n")

        csv_path = Path(__file__).parent / output_file

        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'email',
                'name',
                'google_id',
                'jira_account_id',
                'slack_user_id',
                'team',
                'project_team',
                'weekly_hours_minimum',
                'role',
                'is_active'
            ])
            writer.writeheader()

            for user in users_data:
                # Generate a placeholder Google ID from email
                # Format: email_username (will need to be updated manually)
                google_id_placeholder = f"GOOGLE_ID_{user['email'].split('@')[0]}"

                writer.writerow({
                    'email': user['email'],
                    'name': user['display_name'],
                    'google_id': google_id_placeholder,  # NEEDS MANUAL UPDATE
                    'jira_account_id': user['account_id'],
                    'slack_user_id': user.get('slack_user_id', ''),
                    'team': '',  # Leave blank for manual entry
                    'project_team': '',  # Leave blank for manual entry
                    'weekly_hours_minimum': 32.0,
                    'role': 'member',
                    'is_active': user['active']
                })

        logger.info(f"✅ CSV saved to: {csv_path}")
        logger.info(f"\n📝 NEXT STEPS:")
        logger.info(f"1. Open {csv_path}")
        logger.info(f"2. Replace GOOGLE_ID_* placeholders with actual Google IDs")
        logger.info(f"3. Fill in slack_user_id, team, and project_team columns")
        logger.info(f"4. Run: python scripts/import_users_from_csv.py")

        return csv_path

    def run(self):
        """Main execution."""
        logger.info("=" * 60)
        logger.info("TEMPO USER ID FINDER")
        logger.info("=" * 60)
        logger.info("")

        # Get Tempo users
        account_ids = self.get_tempo_users_from_last_month()

        # Fetch details for each user
        users_data = []
        logger.info("Fetching user details from Jira...\n")

        for i, account_id in enumerate(account_ids, 1):
            logger.info(f"[{i}/{len(account_ids)}] Fetching {account_id}...")

            user_info = self.get_jira_user_info(account_id)

            # Try to find Slack ID
            if user_info['email']:
                slack_id = self.find_slack_user_id(user_info['email'])
                user_info['slack_user_id'] = slack_id

            users_data.append(user_info)

            # Display user info
            logger.info(f"    Name: {user_info['display_name']}")
            logger.info(f"    Email: {user_info['email']}")
            logger.info(f"    Slack ID: {user_info.get('slack_user_id', 'Not found')}")
            logger.info("")

        # Generate CSV
        csv_path = self.generate_csv(users_data)

        return users_data, csv_path


if __name__ == "__main__":
    finder = TempoUserIDFinder()
    users, csv_path = finder.run()

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Found {len(users)} Tempo users")
    logger.info(f"CSV ready at: {csv_path}")
    logger.info(f"{'=' * 60}\n")
