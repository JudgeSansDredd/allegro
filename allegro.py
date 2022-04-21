import math
from datetime import date
from random import randint

from tabulate import tabulate

from allegrosettings import TEMPO_IN_USE
from jiraconnection.jiraaccess import JiraAccess
from timekeeping.jira.jiratimekeeping import JiraTimekeeping
from timekeeping.tempo.tempotimekeeping import TempoAccess

INCREMENT_SECONDS = 900 # 15 minutes
OVERCLOCK_CHANCE = 90 # 20 Percent chance you go over time on an issue
OVERCLOCK_RANGE = 2 # Number of increments possible to overclock

def collectInfo() -> tuple[date, date, list[str]]:
    strStart = input('Start Date [YYYY-MM-DD]: ')
    strEnd = input('End Date [YYYY-MM-DD]: ')
    start = date(*[int(x) for x in strStart.split('-')])
    end = date(*[int(x) for x in strEnd.split('-')])
    issueKeys = []
    t = None
    while t != '':
        t = input('Ticket number (e.g. AGPH-1111) (Empty string to exit): ')
        if t != '':
            issueKeys.append(t.upper())
    return start, end, issueKeys

def getWorkOnIssue(timesheets, issue):
    total = 0
    for sheet in timesheets:
        if issue in sheet.worklogs:
            total += sheet.worklogs[issue]
    return total

def prettyPrintTempoEntries(days, issues, submissions):
    tableData = []
    headers = ['']
    headers.extend(days)
    for issue in issues:
        row = [issue]
        for day in days:
            time = sum(
                [
                    submission['timeSpent']
                    for submission
                    in submissions
                    if submission['day'] == day
                    and submission['issue'] == issue
                ]
            ) / 3600 # Convert to hours
            row.append(time)
        tableData.append(row)
    print(tabulate(tableData, headers=headers))


def main():
    # Access jira and timekeeping
    jira = JiraAccess()
    if TEMPO_IN_USE:
        timekeeping = TempoAccess()
    else:
        timekeeping = JiraTimekeeping()

    # Collect user information
    start, end, issueKeys = collectInfo()

    # Get Jira/Tempo account id
    userId = jira.getAccountId()

    issues = jira.getIssues(issueKeys)
    numIssues = len(issues)
    # numPoints = sum([issue.fields.customfield_10002 for issue in issues])

    # Get worked hours
    timeSheets = timekeeping.getWorkByDay(start, end, userId)

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
            overclockTime = randint(1, OVERCLOCK_RANGE) * INCREMENT_SECONDS if overclocking else 0
            timeSheets.addWork(day, issue, noOverclockTime)
            queuedSubmissions.append({
                'issue': issue,
                'day': day,
                'timeSpent': noOverclockTime + overclockTime
            })

    prettyPrintTempoEntries(timeSheets.getDays(), issues, queuedSubmissions)

    go = input('Do you want to submit these timekeeping entries? y/[n] ')
    if go.upper().strip()[:1] != 'Y':
        return
    for queuedSubmission in queuedSubmissions:
        timekeeping.submitTime(queuedSubmission, userId)


if __name__ == '__main__':
    main()
