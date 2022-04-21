from datetime import datetime, timedelta

from jira import JIRA

from allegrosettings import EMAIL_ADDRESS, JIRA_KEY, JIRA_SERVER, PROJECT_KEY
from timesheets.timesheet import DayTimeSheet, IssueTimeSheet, TimeSheet

from ..interface import TimeKeepingInterface


class JiraTimekeeping(TimeKeepingInterface):
    def __init__(
        self,
        server=JIRA_SERVER,
        emailAddress=EMAIL_ADDRESS,
        token=JIRA_KEY,
        projectKey=PROJECT_KEY
    ):
        self.emailAddress = emailAddress
        self.jira = JIRA({'server': server}, basic_auth=(emailAddress, token))
        self.projectId = self.jira.project(projectKey).id
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
    def getWorkByDay(self, start, end, userId):
        issues = self.jira.search_issues(
            f"project={self.projectId} AND Sprint in openSprints()",
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
