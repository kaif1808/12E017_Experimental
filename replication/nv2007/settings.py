from os import environ

SESSION_CONFIGS = [
    dict(
        name='nv2007_lab',
        display_name='Niederle & Vesterlund 2007 (Lab)',
        num_demo_participants=4,
        app_sequence=['nv2007'],
        use_browser_bots=False,
    ),
    dict(
        name='nv2007_pilot',
        display_name='NV 2007 — Pilot (bots)',
        num_demo_participants=8,
        app_sequence=['nv2007'],
        use_browser_bots=True,
    ),
]

PARTICIPANT_FIELDS = ['problems_1', 'problems_2', 'problems_3']
SESSION_FIELDS = []

LANGUAGE_CODE = 'en'

REAL_WORLD_CURRENCY_CODE = 'USD'
USE_POINTS = False

ROOMS = [
    dict(
        name='econ_lab',
        display_name='Econ Lab',
        participant_label_file='_rooms/lab.txt',
    ),
]

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD', 'changeme')

DEMO_PAGE_INTRO_HTML = ''

SECRET_KEY = environ.get('OTREE_SECRET_KEY', 'fallback-dev-secret-change-in-prod')

INSTALLED_APPS = ['otree']
