#!/usr/bin/env bash
# Apply the buildpack order and PROJECT_PATH from app.json to an existing Heroku app.
# Prerequisites: Heroku CLI, `heroku login`, and HEROKU_APP set to your app name.
#
# Usage:
#   export HEROKU_APP=your-app-name
#   ./scripts/heroku-configure-subdir.sh

set -euo pipefail

APP="${HEROKU_APP:?Set HEROKU_APP to your Heroku application name}"

echo "Configuring $APP: subdir buildpack first, then Python; PROJECT_PATH=replication/nv2007"
heroku buildpacks:clear -a "$APP"
heroku buildpacks:add -i 1 https://github.com/timanovsky/subdir-heroku-buildpack -a "$APP"
heroku buildpacks:add -i 2 heroku/python -a "$APP"
heroku config:set PROJECT_PATH=replication/nv2007 -a "$APP"

echo "Current buildpacks:"
heroku buildpacks -a "$APP"

echo "Done. Deploy from GitHub or run: git push heroku main (if using git remote)"
