#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Apply database migrations
python manage.py migrate

# Create admin user
# python manage.py create_admin

# Import problems
python manage.py import_problems

# Load / refresh the 100-problem beginner curriculum (idempotent, order 15-114)
python manage.py seed_curriculum

# Keep solved-problem stats in sync and close stuck submissions (idempotent)
python manage.py rebuild_progress
