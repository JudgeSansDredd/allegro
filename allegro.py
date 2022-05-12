import math
import os
from configparser import ConfigParser
from datetime import date, timedelta
from pathlib import Path
from random import randint

from tabulate import tabulate
from whiptail import Whiptail

from jiraconnection.jiraaccess import JiraAccess
from timekeeping.jiratimekeeping import JiraTimekeeping

VERSION="1.0.4"
WHIPTAIL_SETTINGS={
    "title": f"Allegro ({VERSION})",
    "width": os.get_terminal_size().columns - 10,
    "height": os.get_terminal_size().lines - 10
}
configPath = Path(f'{Path.home()}/.allegro/config.ini')

def getConfiguration():
    # Whiptail
    wt = Whiptail(**WHIPTAIL_SETTINGS)

    # Get the config object as it exists
    config = ConfigParser()
    config.read(configPath)

    configItems = {
        "JIRA": [
            "JIRA_SERVER",
            "EMAIL_ADDRESS",
            "JIRA_KEY",
            "PROJECT_KEY"
        ],
        "ALLEGRO": [
            "INCREMENT_SECONDS",
            "OVERCLOCK_CHANCE",
            "OVERCLOCK_RANGE",
            "PERCENT_WORKED_PER_DAY"
        ]
    }

    # Set up config and prompt if needed
    for section, options in configItems.items():
        if not config.has_section(section):
            config.add_section(section)
        for option in options:
            if not config.has_option(section, option):
                default = "https://bandwidth-jira.atlassian.net" if option == "JIRA_SERVER" else ""
                value, response = wt.inputbox(f"Enter value for: {option}", default)
                if response == 1:
                    return False
                config.set(section, option, value)


    # Make sure the .allegro directory exists
    configPath.parents[0].mkdir(parents=True, exist_ok=True)
    with open(configPath, 'w', encoding="UTF-8") as conf:
        config.write(conf)

    return True

def collectInfo(jira: JiraAccess):
    wt = Whiptail(**WHIPTAIL_SETTINGS)

    # Today as a date
    today = date.today()
    # If it's sunday, pretend it's the previous saturday
    today = today if today.isoweekday() > 0 else today - timedelta(days=1)
    # Monday of this week
    startOfWeek = today - timedelta(days=(today.isoweekday() - 1))
    # Monday of last week
    startOfLastWeek = startOfWeek - timedelta(days=7)

    # Get Start Date
    res = 1
    while res != 0:
        startMenuRes, res = wt.menu(
            "Pick a start date",
            [
                ["Today", today.isoformat()],
                ["Current Week", startOfWeek.isoformat()],
                ["Last Week", startOfLastWeek.isoformat()],
                ["Custom", "Enter a specific date"]
            ]
        )
        if res == 1:
            return False, False, False
        if startMenuRes == 'Custom':
            strStart, res = wt.inputbox(
                "START Date [YYYY-MM-DD]",
                default=today.isoformat()
            )
            if res == 0:
                start = date(*[int(x) for x in strStart.split('-')])
        elif startMenuRes == 'Today':
            start = today
        elif startMenuRes == 'Current Week':
            start = startOfWeek
        elif startMenuRes == 'Last Week':
            start = startOfLastWeek
        else:
            res = 1

    # Get End Date
    strEnd, res = wt.inputbox(
        "END Date [YYYY-MM-DD]",
        default=today.isoformat()
    )
    if res == 1:
        return False, False, False
    end = date(*[int(x) for x in strEnd.split('-')])

    # Get jira issues
    issues = jira.getIssues()
    issueList = [
        [
            issue.key,
            issue.fields.summary[:70] + '...' if len(issue.fields.summary) > 73 else issue.fields.summary,
            "1" if issue.fields.assignee is not None
            and issue.fields.assignee.emailAddress == jira.emailAddress else "0"
        ]
        for issue in issues
    ]
    selectedKeys, res = wt.checklist(
        "Select worked issues (assigned issues already selected)",
        items=issueList
    )
    if res == 1:
        return False, False, False

    # Filter down to the selected Issues
    selectedIssues = [issue for issue in issues if issue.key in selectedKeys]

    return start, end, selectedIssues

def getWorkOnIssue(timesheets, issue):
    total = 0
    for sheet in timesheets:
        if issue in sheet.worklogs:
            total += sheet.worklogs[issue]
    return total

def askToProceed(days, issues, submissions):
    wt = Whiptail(**WHIPTAIL_SETTINGS)
    tableData = []
    headers = ['']
    headers.extend(issues)
    for day in days:
        row = [day]
        for issue in issues:
            time = sum([
                submission['timeSpent']
                for submission in submissions
                if submission['day'] == day
                and submission['issue'] == issue
            ]) / 3600 # Convert to hours
            row.append(time)
        tableData.append(row)
    tableString = tabulate(tableData, headers=headers)
    question = "Do you want to submit the following times?"
    return not wt.yesno(
        f"{question}\n\n\n\n{tableString}",
        default="no"
    )

def main():
    # Make sure our config file is written and has necessary info
    proceed = getConfiguration()
    if not proceed:
        return

    # Get settings
    config = ConfigParser()
    config.read(configPath)
    overclockRange = int(config.get('ALLEGRO', 'OVERCLOCK_RANGE'))
    incrementSeconds = int(config.get('ALLEGRO', 'INCREMENT_SECONDS'))
    overclockChance = int(config.get('ALLEGRO', 'OVERCLOCK_CHANCE'))

    # Access jira and timekeeping
    jira = JiraAccess(configPath)
    timekeeping = JiraTimekeeping(configPath)

    # Collect user information
    start, end, issues = collectInfo(jira)
    # Did they hit cancel?
    if not start:
        return

    numIssues = len(issues)
    # numPoints = sum([issue.fields.customfield_10002 for issue in issues])

    # Get worked hours
    timeSheets = timekeeping.getWorkByDay(start, end)

    # Time per issue
    totalNeeded = timeSheets.getTotalNeeded(issues)
    requiredPerIssue = totalNeeded / numIssues
    timeSheets.setRequiredPerIssue(requiredPerIssue)

    # Queue up submissions
    queuedSubmissions = []
    for issue in issues:
        for day in timeSheets.getDays():
            allowed = timeSheets.getAllowedWork(day, issue)
            if allowed == 0:
                continue
            numIncrements = math.ceil(allowed / incrementSeconds)
            noOverclockTime = numIncrements * incrementSeconds
            overclocking = randint(1, 100) <= overclockChance
            overclockTime = randint(1, overclockRange) * incrementSeconds if overclocking else 0
            timeSheets.addWork(day, issue, noOverclockTime)
            queuedSubmissions.append({
                'issue': issue,
                'day': day,
                'timeSpent': noOverclockTime + overclockTime
            })

    proceed = askToProceed(timeSheets.getDays(), issues, queuedSubmissions)

    if proceed:
        for queuedSubmission in queuedSubmissions:
            timekeeping.submitTime(queuedSubmission)

if __name__ == '__main__':
    main()
