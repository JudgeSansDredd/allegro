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
to make sure you enter the required information correctly. **Allegro does not fail gracefully.** You will
have a chance to give final approval before it submits anything to jira, though, so you're safe
until that point.

## Installing, a.k.a. easy mode
macOs
```
sudo curl https://raw.githubusercontent.com/JudgeSansDredd/allegro/master/dist/macos/allegro --output /usr/local/bin/allegro && sudo chmod +x /usr/local/bin/allegro
```

debian
```
sudo curl https://raw.githubusercontent.com/JudgeSansDredd/allegro/master/dist/debian/allegro --output /usr/local/bin/allegro && sudo chmod +x /usr/local/bin/allegro
```

## To Develop, or Run from Source

1. _Optional:_ Create a python virtual environment, then activate it

   ```
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install python requirements

   ```
   pip3 install -r requirements.txt
   ```

3. Ready to run!
   ```
   python3 allegro.py
   ```

## Building from source

1. Install `pyinstaller`

   ```
   pip3 install pyinstaller
   ```

2. Create binary

   ```
   pyinstaller allegro.py --onefile --distpath ./dist/{YOUR_ARCHITECTURE}
   ```

3. Binary now exists at `./dist/allegro`
