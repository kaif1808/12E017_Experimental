#!/usr/bin/env bash
# Apply the buildpack order and PROJECT_PATH to an existing Heroku app.
#
# The timanovsky subdir buildpack reads PROJECT_PATH only from Heroku config vars
# (ENV_DIR/PROJECT_PATH at compile time). app.json "env" is NOT auto-synced for
# GitHub-connected apps—you must set this on the app (this script or Dashboard).
#
# Prerequisites: Heroku CLI, `heroku login`, and HEROKU_APP set to your app name.
#
# Usage:
#   export HEROKU_APP=your-app-name
#   ./scripts/heroku-configure-subdir.sh

set -euo pipefail

APP="${HEROKU_APP:?Set HEROKU_APP to your Heroku application name}"

echo "Configuring $APP: PROJECT_PATH (required by subdir buildpack), then buildpack order"
heroku config:set PROJECT_PATH=replication/nv2007 -a "$APP"

heroku buildpacks:clear -a "$APP"
heroku buildpacks:add -i 1 https://github.com/timanovsky/subdir-heroku-buildpack -a "$APP"
heroku buildpacks:add -i 2 heroku/python -a "$APP"

echo "Current buildpacks:"
heroku buildpacks -a "$APP"

echo "Done. Deploy from GitHub or run: git push heroku main (if using git remote)"
