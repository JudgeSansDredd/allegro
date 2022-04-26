import math
from configparser import ConfigParser
from datetime import date
from pathlib import Path
from random import randint

from tabulate import tabulate
from whiptail import Whiptail

from jiraconnection.jiraaccess import JiraAccess
from timekeeping.jiratimekeeping import JiraTimekeeping

WHIPTAIL_SETTINGS={
    "title": "Allegro, a Fast Tempo",
    "width": 75
}
configPath = Path(f'{Path.home()}/.allegro/config.ini')

def getConfiguration():
    # Whiptail
    wt = Whiptail(WHIPTAIL_SETTINGS)

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
            "OVERCLOCK_RANGE"
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
    configPath.parents[0].mkdir(parents=True)
    with open(configPath, 'w', encoding="UTF-8") as conf:
        config.write(conf)

    return True

def collectInfo(jira):
    wt = Whiptail(**WHIPTAIL_SETTINGS)
    today = date.today().isoformat()

    # Get Start Date
    strStart, res = wt.inputbox("Start Date [YYYY-MM-DD]", default=today)
    if res == 1:
        return False, False, False
    start = date(*[int(x) for x in strStart.split('-')])

    # Get End Date
    strEnd, res = wt.inputbox("End Date [YYYY-MM-DD]", default=today)
    if res == 1:
        return False, False, False
    end = date(*[int(x) for x in strEnd.split('-')])

    # Get jira issues
    issues = jira.getIssues()
    issueList = [
        [
            issue.key,
            issue.fields.summary[:47] + '...' if len(issue.fields.summary) > 50 else issue.fields.summary,
            "1" if issue.fields.assignee.emailAddress == EMAIL_ADDRESS else "0"
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
    return not wt.yesno(tabulate(tableData, headers=headers), default="no")

def main():
    # Make sure our config file is written and has necessary info
    cancelled = getConfiguration()
    if cancelled:
        return

    # Get settings
    config = ConfigParser()
    config.read(configPath)

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
            numIncrements = math.ceil(allowed / INCREMENT_SECONDS)
            noOverclockTime = numIncrements * INCREMENT_SECONDS
            overclocking = randint(1, 100) <= OVERCLOCK_CHANCE
            overclockRange = int(config.get('ALLEGRO', 'OVERCLOCK_RANGE'))
            overclockTime = randint(1, overclockRange) * INCREMENT_SECONDS if overclocking else 0
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
