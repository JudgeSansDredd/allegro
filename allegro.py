import http.client
import json
import math
from datetime import date, datetime, timedelta
from random import randint

from tabulate import tabulate

from allegrosettings import EMAIL_ADDRESS, JIRA_KEY, JIRA_SERVER, PROJECT_ID
from jiraconnection import JIRA

INCREMENT_SECONDS = 900 # 15 minutes
OVERCLOCK_CHANCE = 90 # 20 Percent chance you go over time on an issue
OVERCLOCK_RANGE = 2 # Number of increments possible to overclock




class DayTimeSheet():
    def __init__(self, day, required, worklogs):
        self.day = day
        self.required = required
        self.worklogs = worklogs
        self._calcDayData()

    def __str__(self):
        out = {
            'date': self.day,
            'required': self.required,
            'worked': self.worked,
            'needed': self.needed,
            'worklogs': self.worklogs
        }
        return json.dumps(out, indent=4)

    def addWork(self, issue, time):
        if issue in self.worklogs:
            current = self.worklogs[issue]
            new = current + time
            self.worklogs[issue] = new
        else:
            self.worklogs[issue] = time
        self._calcDayData()

    def getWork(self, issue):
        return self.worklogs[issue] if issue in self.worklogs else 0

    def _calcDayData(self):
        self.worked = sum(self.worklogs.values())
        self.needed = self.required - self.worked

    def getWorkedMisc(self, issues):
        return sum([worklog for issue, worklog in self.worklogs.items() if issue not in issues])

class IssueTimeSheet():
    def __init__(self, issue, worked):
        self.issue = issue
        self.worked = worked

    def addWork(self, time):
        self.worked += time

class TimeSheet():
    def __init__(self, dayTimeSheets, issueTimeSheets):
        self.requiredPerIssue = None
        self.dayTimeSheets = dayTimeSheets
        self.issueTimeSheets = issueTimeSheets

    def setRequiredPerIssue(self, time):
        self.requiredPerIssue = time

    def getDays(self) -> list[str]:
        return self.dayTimeSheets.keys()

    def getTotalNeeded(self, issues) -> int:
        required = sum(sheet.required for sheet in self.dayTimeSheets.values())
        worked   = sum([sheet.getWorkedMisc(issues) for sheet in self.dayTimeSheets.values()])
        needed = required - worked
        return needed if needed > 0 else 0

    def addWork(self, day, issue, time):
        self.dayTimeSheets[day].addWork(issue, time)
        if issue in self.issueTimeSheets:
            self.issueTimeSheets[issue].addWork(time)
        else:
            self.issueTimeSheets[issue] = IssueTimeSheet(issue, time)

    def getAllowedWork(self, day, issue) -> int:
        if self.requiredPerIssue is None:
            raise Exception('You have not set the required per issue variable')
        dayNeeded = self.dayTimeSheets[day].needed
        if issue in self.issueTimeSheets:
            issueWorked = self.issueTimeSheets[issue].worked
        else:
            issueWorked = 0
        issueNeeded = self.requiredPerIssue - issueWorked
        allowed = min(dayNeeded, issueNeeded)
        return allowed if allowed > 0 else 0

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
    timekeeping = JiraTimekeeping()
    # timekeeping = TempoAccess()

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
