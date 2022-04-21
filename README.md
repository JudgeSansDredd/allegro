# Allegro, for Fast Timekeeping

[![forthebadge](https://forthebadge.com/images/badges/contains-technical-debt.svg)](https://forthebadge.com)

## About Allegro

> What is this thing?

This is Allegro, built to make time entry for busy developers less of a headache.
It will look for any tickets you're assigned in Jira for the currently open sprints,
ask you for any other tickets you've worked on, then it will make sure you've logged
8 hours a day to tickets, spread evenly across them.

> Does timekeeping actually take that much time?

Maybe not on a daily basis, but it can add up, certainly. Especially when you're trying
to recall what you worked on last week.

> This is ridiculous.

Thanks, I'm a ridiculous person, so that tracks.

> You're gonna break my computer, aren't you?

This isn't user-proof code. You'll need to use your years of experience and highly honed developer senses
to make sure you enter the required information correctly. **Allegro does not fail gracefully.** You will have a chance to give
final approval before it submits anything to jira or tempo, though, so you're safe until that point.

## Setup

1. _Optional:_ Create a python virtual environment, then activate it

   ```
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install python requirements

   ```
   pip3 install -r requirements.txt
   ```

3. Create `allegrosettings.py` to hold the settings you want Allegro to use. Here's a template:

   ```
   JIRA_SERVER='https://your-company-jira-address.atlassian.net'
   EMAIL_ADDRESS='your-email-address@example.com'
   JIRA_KEY='your-jira-api-key'
   PROJECT_KEY="ABC" # This will be the letter designation on all of your tickets

   TEMPO_IN_USE=False # Does your company use Tempo to track time?
   TEMPO_TOKEN='' # Tempo has its own api, you'll need a token there, too

   INCREMENT_SECONDS = 900 # 15 minutes, i.e. how grandular should we enter time?
   OVERCLOCK_CHANCE = 90 # 20 Percent chance you go over time on an issue
   OVERCLOCK_RANGE = 2 # Number of increments possible to overclock
   ```
