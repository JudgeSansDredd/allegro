import http.client
import json
import math
from datetime import date, datetime, timedelta
from random import randint

from jira import JIRA
from tabulate import tabulate

from jirasettings import (EMAIL_ADDRESS, JIRA_KEY, JIRA_SERVER, PROJECT_ID,
                          TEMPO_TOKEN)

INCREMENT_SECONDS = 900 # 15 minutes
OVERCLOCK_CHANCE = 90 # 20 Percent chance you go over time on an issue
OVERCLOCK_RANGE = 2 # Number of increments possible to overclock

class TimeKeepingInterface():
    def _getWorkDays(self, start, end):
        raise Exception('Method not implemented')
    def getWorkByDay(self, start, end, userId):
        raise Exception('Method not implemented')
    def submitTime(self, submission, userId):
        raise Exception('Method not implemented')


class TempoAccess(TimeKeepingInterface):
    def __init__(self, token=TEMPO_TOKEN):
        self.token = token

    def _getWorkDays(self, start, end):
        conn = http.client.HTTPSConnection("api.tempo.io")
        headersList = {
        "Accept": "*/*",
        "User-Agent": "Allegro Python Script",
        "Authorization": f"Bearer {self.token}"
        }

        payload = ""

        strStart = f"{start.year}-{start.month}-{start.day}"
        strEnd = f"{end.year}-{end.month}-{end.day}"

        conn.request(
            "GET",
            f"/core/3/user-schedule?from={strStart}&to={strEnd}",
            payload,
            headersList
        )
        response = conn.getresponse()
        result = response.read()

        parsed = json.loads(result.decode('utf-8'))
        days = parsed['results']
        return [
            {
                'date': day['date'],
                'required': day['requiredSeconds']
            }
            for day in days
            if day['type'].upper() == 'WORKING_DAY'
        ]

    def getWorkByDay(self, start, end, userId):
        conn = http.client.HTTPSConnection("api.tempo.io")

        headersList = {
        "Accept": "*/*",
        "User-Agent": "Allegro Python Script",
        "Authorization": f"Bearer {self.token}"
        }

        payload = ""

        strStart = f"{start.year}-{start.month}-{start.day}"
        strEnd = f"{end.year}-{end.month}-{end.day}"

        conn.request(
            "GET",
            f"/core/3/worklogs/user/{userId}?from={strStart}&to={strEnd}",
            payload,
            headersList
        )
        response = conn.getresponse()
        result = response.read()
        parsed = json.loads(result.decode('utf-8'))
        worklogs = parsed['results']

        dates = self._getWorkDays(start, end)
        workByDate = {}
        workByIssue = {}

        for d in dates:
            dateWorklogs = [log for log in worklogs if log['startDate'] == d['date']]
            byKey = {}
            for log in dateWorklogs:
                if log['issue']['key'] not in byKey:
                    byKey[log['issue']['key']] = log['timeSpentSeconds']
                else:
                    byKey[log['issue']['key']] += log['timeSpentSeconds']
            workByDate[d['date']] = (DayTimeSheet(d['date'], d['required'], byKey))
            for issue, time in byKey.items():
                if issue not in workByIssue:
                    workByIssue[issue] = IssueTimeSheet(issue, time)
                else:
                    workByIssue[issue].addWork(time)
        return TimeSheet(workByDate, workByIssue)

    def submitTime(self, submission, userId):
        issue = submission['issue']
        day = submission['day']
        timeSpent = submission['timeSpent']

        if timeSpent == 0:
            return

        print(f'Submitting {timeSpent / 3600} for {issue} on {day}... ', end='')

        conn = http.client.HTTPSConnection("api.tempo.io")

        headersList = {
        "Accept": "*/*",
        "User-Agent": "Allegro Python Script",
        "Authorization": f"Bearer {self.token}",
        "Content-Type": "application/json"
        }

        params = {
            'issueKey': issue,
            'timeSpentSeconds': timeSpent,
            'startDate': day,
            'startTime': '12:00:00',
            'authorAccountId': userId
        }

        conn.request(
            "POST",
            "/core/3/worklogs",
            json.dumps(params),
            headersList
        )
        conn.getresponse()

        print('Done')

class JiraTimekeeping(TimeKeepingInterface):
    def __init__(self, server=JIRA_SERVER, emailAddress=EMAIL_ADDRESS, token=JIRA_KEY):
        self.emailAddress = emailAddress
        self.jira = JIRA({'server': server}, basic_auth=(emailAddress, token))
    def _getWorkDays(self, start, end):
        # TODO: Account for holidays
        return [
            {
                'date': (start + timedelta(days=i)).isoformat(),
                'required': 8 * 3600
            }
            for i
            in range((end - start).days + 1)
            if (start + timedelta(days=i)).isoweekday() > 0
            and (start + timedelta(days=i)).isoweekday() < 6
        ]
    def getWorkByDay(self, start, end, userId, projectId=PROJECT_ID):
        issues = self.jira.search_issues(
            f"project={projectId} AND Sprint in openSprints()",
            maxResults=1000
        )

        allWorklogsByIssue = [
            self.jira.worklogs(issue.key)
            for issue in issues
        ]
        worklogs = [
            worklog
            for worklogsForIssue in allWorklogsByIssue
            for worklog in worklogsForIssue
            if worklog.author.emailAddress.lower() == self.emailAddress.lower()
        ]

        dates = self._getWorkDays(start, end)
        workByDate = {}
        workByIssue = {}

        for d in dates:
            dateWorklogs = [
                log
                for log in worklogs
                if log.started.split('T')[0] == d['date']
            ]
            byKey = {}
            for log in dateWorklogs:
                issueKey = self.jira.issue(log.issueId).key
                if issueKey not in byKey:
                    byKey[issueKey] = log.timeSpentSeconds
                else:
                    byKey[issueKey] += log.timeSpentSeconds
            workByDate[d['date']] = (DayTimeSheet(d['date'], d['required'], byKey))
            for issue, time in byKey.items():
                if issue not in workByIssue:
                    workByIssue[issue] = IssueTimeSheet(issue, time)
                else:
                    workByIssue[issue].addWork(time)
        return TimeSheet(workByDate, workByIssue)

    def submitTime(self, submission, userId):
        issue = submission['issue']
        day = submission['day']
        timeSpent = submission['timeSpent']

        if timeSpent == 0:
            return

        print(f'Submitting {timeSpent / 3600} for {issue} on {day}... ', end='')

        # NOTE: We're making the assumption that the largest time will be less than one day
        params = {
            "issue": issue,
            "started": datetime.fromisoformat(day),
            "timeSpentSeconds": timeSpent,
            "newEstimate": "0m"
        }
        self.jira.add_worklog(**params)

        print('Done')

class JiraAccess():
    def __init__(
        self,
        server=JIRA_SERVER,
        emailAddress=EMAIL_ADDRESS,
        token=JIRA_KEY,
        projectId=PROJECT_ID
    ):
        self.jira = JIRA({'server': server}, basic_auth=(emailAddress, token))
        self.projectId = projectId

    def getAccountId(self) -> str:
        return self.jira.myself()['accountId']

    def getAllSubtasks(self, issueKeys) -> list[str]:
        issues = self.getIssues(issueKeys)
        allFilteredSubtasks = []
        for issue in issues:
            subtasks = [
                st.key
                for st
                in self._getSubtasksAsIssues(issue)
                if st.fields.assignee is not None
                and st.fields.assignee.emailAddress.lower() == EMAIL_ADDRESS.lower()
            ]
            subtasks.reverse()
            allFilteredSubtasks.extend(subtasks)
        return allFilteredSubtasks

    def _getSubtasksAsIssues(self, parentIssue):
        # Grab the subtasks
        subtaskIds = [subtask.key for subtask in parentIssue.fields.subtasks]
        return self.getIssues(subtaskIds) if subtaskIds else []

    def getIssues(self, issueKeys: list[str]):
        keyString = ', '.join([f'\"{key}\"' for key in issueKeys])
        keyQuery = f"key IN ({keyString})"
        sprintQuery = f"project={self.projectId} AND Sprint in openSprints() AND Assignee = currentUser()"
        if len(issueKeys) > 0:
            queryString = f"({keyQuery}) OR ({sprintQuery})"
        else:
            queryString = sprintQuery
        return self.jira.search_issues(
            queryString,
            maxResults=False
        )

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
