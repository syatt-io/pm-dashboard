#!/usr/bin/env python3
"""
Update TEMPO_API_TOKEN in DigitalOcean App Platform

This script updates the TEMPO_API_TOKEN environment variable for all services
in the app to fix the 401 Unauthorized error in the nightly Tempo sync job.
"""

import json
import subprocess
import sys

APP_ID = "a2255a3b-23cc-4fd0-baa8-91d622bb912a"
NEW_TOKEN = "PBl9AfH5qz7MuDjh2brtBnUt2SgzgQ-us"


def get_app_spec():
    """Get the current app spec from DigitalOcean."""
    print("📥 Fetching current app spec...")
    result = subprocess.run(
        ["doctl", "apps", "spec", "get", APP_ID, "--format", "json"],
        capture_output=True,
        text=True,
        check=True
    )
    return json.loads(result.stdout)


def update_tempo_token_in_spec(spec):
    """Update TEMPO_API_TOKEN in all services."""
    print(f"🔧 Updating TEMPO_API_TOKEN in app spec...")

    updated_count = 0

    # Update in services
    if "services" in spec:
        for service in spec["services"]:
            if "envs" in service:
                for env in service["envs"]:
                    if env["key"] == "TEMPO_API_TOKEN":
                        old_value = env.get("value", "")
                        env["value"] = NEW_TOKEN
                        env["scope"] = "RUN_AND_BUILD_TIME"
                        env["type"] = "SECRET"
                        updated_count += 1
                        print(f"  ✓ Updated TEMPO_API_TOKEN in service '{service['name']}'")

    # Update in workers (if any)
    if "workers" in spec:
        for worker in spec["workers"]:
            if "envs" in worker:
                for env in worker["envs"]:
                    if env["key"] == "TEMPO_API_TOKEN":
                        env["value"] = NEW_TOKEN
                        env["scope"] = "RUN_AND_BUILD_TIME"
                        env["type"] = "SECRET"
                        updated_count += 1
                        print(f"  ✓ Updated TEMPO_API_TOKEN in worker '{worker['name']}'")

    print(f"\n📊 Total updates: {updated_count} TEMPO_API_TOKEN values")
    return spec, updated_count


def save_and_update_spec(spec):
    """Save the updated spec and update the app."""
    print("\n💾 Saving updated spec...")

    # Save to temp file
    temp_file = "/tmp/updated_app_spec.json"
    with open(temp_file, "w") as f:
        json.dump(spec, f, indent=2)

    print(f"📝 Spec saved to {temp_file}")

    # Update the app
    print(f"\n🚀 Updating app {APP_ID}...")
    print("⚠️  This will trigger a new deployment...")

    # Ask for confirmation
    response = input("\nProceed with update? (yes/no): ")
    if response.lower() != "yes":
        print("❌ Update cancelled")
        return False

    try:
        result = subprocess.run(
            ["doctl", "apps", "update", APP_ID, "--spec", temp_file],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ App updated successfully!")
        print("\n📋 Deployment started. Check status with:")
        print(f"   doctl apps list | grep agent-pm")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error updating app: {e.stderr}")
        return False


def main():
    print("=== DigitalOcean App Platform - Update TEMPO_API_TOKEN ===\n")

    try:
        # Get current spec
        spec = get_app_spec()

        # Update token
        updated_spec, count = update_tempo_token_in_spec(spec)

        if count == 0:
            print("\n⚠️  No TEMPO_API_TOKEN found in app spec")
            sys.exit(1)

        # Save and update
        if save_and_update_spec(updated_spec):
            print("\n✅ Update complete! The app will redeploy with the new token.")
            print("\n📌 Next steps:")
            print("  1. Wait for deployment to complete (~3-5 minutes)")
            print("  2. Monitor deployment: doctl apps list | grep agent-pm")
            print("  3. Check logs: doctl apps logs", APP_ID, "app --type run --tail=100")
            print("  4. Test the sync job manually (see README)")
        else:
            print("\n❌ Update failed")
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        print(f"stderr: {e.stderr if hasattr(e, 'stderr') else 'N/A'}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
